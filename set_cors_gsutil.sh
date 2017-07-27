
# See instructions here: https://cloud.google.com/storage/docs/cross-origin
# and see also https://stackoverflow.com/questions/38618666/googe-storage-argumentexception-when-setting-cors-config

echo '[{
    "origin": ["*"],
    "method": ["GET"],
    "maxAgeSeconds": 3600
}]' > cors-json-amend.json

gsutil cors set cors-json-amend.json gs://ns697-amend


