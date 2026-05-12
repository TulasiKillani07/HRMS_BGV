import cloudinary
import cloudinary.uploader
import cloudinary.api

# config.py
SUREPASS_BASE_URL = "https://sandbox.surepass.io/api/v1"
SUREPASS_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJmcmVzaCI6ZmFsc2UsImlhdCI6MTc2MzQ0NTU2OSwianRpIjoiZmEyOTkyYTEtNTFhMS00ZTgzLWEyMWItZjU4MTA1OTUxZjM3IiwidHlwZSI6ImFjY2VzcyIsImlkZW50aXR5IjoiZGV2LnRocmVzaGluZ0BzdXJlcGFzcy5pbyIsIm5iZiI6MTc2MzQ0NTU2OSwiZXhwIjoxNzY2MDM3NTY5LCJlbWFpbCI6InRocmVzaGluZ0BzdXJlcGFzcy5pbyIsInRlbmFudF9pZCI6Im1haW4iLCJ1c2VyX2NsYWltcyI6eyJzY29wZXMiOlsidXNlciJdfX0.-x0-DbYQFrCKiEvt_7JorRHgf_N4T9oXvULZIrebiGw"

cloudinary.config( 
    cloud_name = "dz0nugtfe", 
    api_key = "823959276223763", 
    api_secret = "3WL9jN__Me9PG0tn6xQej9R37cE",
    secure = True
)
