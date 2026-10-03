import boto3

BUCKET_NAME = "trial-sb"
REGION = "us-east-2"

session = boto3.Session(
    profile_name="default",
    region_name=REGION
)

s3 = session.client("s3")

response = s3.list_objects_v2(
    Bucket=BUCKET_NAME,
    MaxKeys=10
)

print(response)

print()

BUCKET_NAME = 'trial-sb'

try:
    response = s3.list_objects_v2(Bucket=BUCKET_NAME)

    print(f"Files in bucket '{BUCKET_NAME}':")
    if 'Contents' in response:
        for obj in response['Contents']:
            print(f" - {obj['Key']}")
    else:
        print("The bucket is currently empty.")

except Exception as e:
    print(f"Error accessing bucket: {e}")
