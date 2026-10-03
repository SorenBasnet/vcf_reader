import boto3

session = boto3.Session()

print("Python credentials/profile:", session.profile_name)
print("Region:", session.region_name)

sts = session.client("sts")
print(sts.get_caller_identity())
