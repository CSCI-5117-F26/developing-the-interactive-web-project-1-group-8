import os
import boto3
from io import BytesIO
from uuid import uuid4
from PIL import Image, ImageOps


MAX_AVATAR_BYTES = 5 * 1024 * 1024


# https://pillow.readthedocs.io/en/stable/reference/ImageOps.html#PIL.ImageOps.exif_transpose
# https://pillow.readthedocs.io/en/stable/reference/Image.html
def prepare_avatar(image):
    image.load()
    image = ImageOps.exif_transpose(image)
    image.thumbnail((512, 512))

    image_with_alpha = image.convert("RGBA")
    alpha_channel = image_with_alpha.getchannel("A")
    avatar_image = Image.new("RGB", image_with_alpha.size, "white")
    avatar_image.paste(image_with_alpha, mask=alpha_channel)

    output = BytesIO()
    avatar_image.save(output, format="JPEG", quality=75)
    return output.getvalue()


# https://developers.cloudflare.com/r2/examples/aws/boto3/
def get_avatar_storage():
    client = boto3.client(
        "s3",
        endpoint_url=os.environ["R2_ENDPOINT_URL"],
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        region_name="auto",
    )
    return client, os.environ["R2_BUCKET_NAME"]


def upload_avatar(image_data, user_id):
    filename = uuid4().hex + ".jpg"
    object_key = f"avatars/{user_id}/{filename}"

    client, bucket_name = get_avatar_storage()
    client.put_object(
        Bucket=bucket_name,
        Key=object_key,
        Body=image_data,
        ContentType="image/jpeg",
    )
    return object_key


def download_avatar(object_key):
    client, bucket_name = get_avatar_storage()
    response = client.get_object(Bucket=bucket_name, Key=object_key)
    body = response["Body"]
    try:
        image_data = body.read()
    finally:
        body.close()
    return image_data


def delete_avatar(object_key):
    client, bucket_name = get_avatar_storage()
    client.delete_object(Bucket=bucket_name, Key=object_key)
