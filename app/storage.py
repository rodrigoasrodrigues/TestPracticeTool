import mimetypes
import os
import uuid
from urllib.parse import quote, urlparse

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from flask import current_app, url_for

_DEFAULT_ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}


def _allowed_extensions():
    return current_app.config.get('ALLOWED_EXTENSIONS', _DEFAULT_ALLOWED_EXTENSIONS)


def _parse_s3_uri(s3_uri):
    parsed = urlparse((s3_uri or '').strip())
    if parsed.scheme.lower() != 's3' or not parsed.netloc:
        raise ValueError('IMAGE_S3_PATH deve estar no formato s3://bucket/caminho-opcional')

    bucket = parsed.netloc.strip()
    key = parsed.path.lstrip('/')
    return bucket, key


def is_s3_storage_enabled():
    return bool((current_app.config.get('IMAGE_S3_PATH') or '').strip())


def _parse_base_s3_path():
    raw_path = (current_app.config.get('IMAGE_S3_PATH') or '').strip()
    if not raw_path:
        return None, None

    bucket, prefix = _parse_s3_uri(raw_path)
    return bucket, prefix.rstrip('/')


def _build_s3_key(filename):
    bucket, prefix = _parse_base_s3_path()
    if not bucket:
        raise ValueError('IMAGE_S3_PATH não está configurada.')

    key = '/'.join(part for part in [prefix, filename] if part)
    return bucket, key


def _get_s3_client():
    client_kwargs = {}
    region = current_app.config.get('APP_AWS_REGION') or current_app.config.get('AWS_REGION')
    endpoint_url = current_app.config.get('AWS_S3_ENDPOINT_URL')
    access_key_id = current_app.config.get('APP_AWS_ACCESS_KEY_ID')
    secret_access_key = current_app.config.get('APP_AWS_SECRET_ACCESS_KEY')
    session_token = current_app.config.get('APP_AWS_SESSION_TOKEN')

    if region:
        client_kwargs['region_name'] = region
    if endpoint_url:
        client_kwargs['endpoint_url'] = endpoint_url
    if access_key_id and secret_access_key:
        client_kwargs['aws_access_key_id'] = access_key_id
        client_kwargs['aws_secret_access_key'] = secret_access_key
        if session_token:
            client_kwargs['aws_session_token'] = session_token

    return boto3.client('s3', **client_kwargs)


def _guess_content_type(filename):
    return mimetypes.guess_type(filename or '')[0] or 'application/octet-stream'


def save_image(file_storage):
    ext = os.path.splitext(file_storage.filename or '')[1].lower().lstrip('.')
    if ext not in _allowed_extensions():
        raise ValueError(f'Extensão de imagem não permitida: .{ext}')

    filename = f"{uuid.uuid4().hex}.{ext}"

    if is_s3_storage_enabled():
        bucket, key = _build_s3_key(filename)
        try:
            file_storage.stream.seek(0)
            _get_s3_client().upload_fileobj(
                file_storage.stream,
                bucket,
                key,
                ExtraArgs={'ContentType': file_storage.mimetype or _guess_content_type(filename)},
            )
        except (OSError, BotoCoreError, ClientError) as exc:
            raise RuntimeError(f'Falha ao enviar imagem para o S3: {exc}') from exc
        return f's3://{bucket}/{key}'

    upload_folder = current_app.config['UPLOAD_FOLDER']
    os.makedirs(upload_folder, exist_ok=True)
    file_storage.save(os.path.join(upload_folder, filename))
    return filename


def save_image_bytes(original_name, content_bytes):
    ext = os.path.splitext(os.path.basename(original_name or ''))[1].lower().lstrip('.')
    if ext not in _allowed_extensions():
        raise ValueError(f'Extensão de imagem não permitida: .{ext}')

    filename = f"{uuid.uuid4().hex}.{ext}"

    if is_s3_storage_enabled():
        bucket, key = _build_s3_key(filename)
        try:
            _get_s3_client().put_object(
                Bucket=bucket,
                Key=key,
                Body=content_bytes,
                ContentType=_guess_content_type(filename),
            )
        except (BotoCoreError, ClientError) as exc:
            raise RuntimeError(f'Falha ao enviar imagem importada para o S3: {exc}') from exc
        return f's3://{bucket}/{key}'

    upload_folder = current_app.config['UPLOAD_FOLDER']
    os.makedirs(upload_folder, exist_ok=True)
    file_path = os.path.join(upload_folder, filename)
    with open(file_path, 'wb') as img_file:
        img_file.write(content_bytes)
    return filename


def read_image_bytes(image_path):
    if not image_path:
        return None

    if str(image_path).lower().startswith('s3://'):
        bucket, key = _parse_s3_uri(image_path)
        try:
            response = _get_s3_client().get_object(Bucket=bucket, Key=key)
            return response['Body'].read()
        except ClientError as exc:
            error_code = exc.response.get('Error', {}).get('Code')
            if error_code in {'NoSuchKey', '404', 'NotFound'}:
                return None
            raise RuntimeError(f'Falha ao ler imagem do S3: {exc}') from exc
        except BotoCoreError as exc:
            raise RuntimeError(f'Falha ao ler imagem do S3: {exc}') from exc

    source_path = os.path.join(current_app.config['UPLOAD_FOLDER'], image_path)
    if not os.path.exists(source_path):
        return None

    with open(source_path, 'rb') as img_file:
        return img_file.read()


def delete_image(image_path):
    if not image_path:
        return

    if str(image_path).lower().startswith('s3://'):
        bucket, key = _parse_s3_uri(image_path)
        try:
            _get_s3_client().delete_object(Bucket=bucket, Key=key)
        except ClientError as exc:
            error_code = exc.response.get('Error', {}).get('Code')
            if error_code not in {'NoSuchKey', '404', 'NotFound'}:
                raise RuntimeError(f'Falha ao remover imagem do S3: {exc}') from exc
        except BotoCoreError as exc:
            raise RuntimeError(f'Falha ao remover imagem do S3: {exc}') from exc
        return

    local_path = os.path.join(current_app.config['UPLOAD_FOLDER'], image_path)
    if os.path.exists(local_path):
        os.remove(local_path)


def get_image_url(image_path):
    if not image_path:
        return ''

    image_path = str(image_path)
    if image_path.startswith(('http://', 'https://')):
        return image_path

    if image_path.lower().startswith('s3://'):
        bucket, key = _parse_s3_uri(image_path)
        expires_in = int(current_app.config.get('IMAGE_S3_URL_EXPIRATION', 3600))
        try:
            return _get_s3_client().generate_presigned_url(
                'get_object',
                Params={'Bucket': bucket, 'Key': key},
                ExpiresIn=expires_in,
            )
        except (BotoCoreError, ClientError):
            return f'https://{bucket}.s3.amazonaws.com/{quote(key, safe="/")}'

    return url_for('static', filename=f'uploads/{image_path}')
