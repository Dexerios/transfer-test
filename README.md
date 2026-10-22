# FSR transfer service

Receives JSON uploads from the legacy Roblox game and writes the existing slot
payload to universe `3064619271`, datastore `TransferStore`, scope `global`, using
the unchanged `Player_<UserId>` key format. `/` remains the health endpoint.

`ROBLOX_API_KEY` and `TRANSFER_UPLOAD_SECRET` are required environment variables.
Never place their values in this repository. Uploads authenticate through the
`X-Transfer-Secret` header. Requests are limited to 4 MiB before JSON parsing;
serialized datastore entries retain the existing 3,500,000-byte limit.

## Tests

Install `requirements.txt`, then run `python -m unittest discover -s tests -v`.
Tests use dummy credentials and mocked Roblox requests; they never write player
data. GitHub also runs them inside the production Docker image on Linux.

## Coordinated credential rotation

Treat credentials previously stored in Railway as potentially exposed. Minimize
the overlap below: accepting an old upload secret continues to trust that secret
until it is removed. If abuse is suspected, stop accepting it immediately, even
if that briefly interrupts transfers.

1. Deploy this code with the existing nonempty credentials first. Confirm the
   deployment is active and existing transfers still succeed. Do not continue
   while Railway cannot activate deployments for this project.
2. Create a replacement Roblox Open Cloud key with only the access needed by this
   service: standard datastore entry writes to the remaster universe and, where
   supported, only `TransferStore`. Preserve necessary IP restrictions. Do not
   regenerate or revoke the currently used key yet.
3. Set Railway's `ROBLOX_API_KEY` to the replacement and redeploy. Verify a real
   intended transfer succeeds. A healthy `/` response alone does not verify the
   key's datastore permissions. Then revoke the old Roblox key.
4. Generate a new random upload secret in a password manager. In one Railway
   variable update, put the current upload secret in
   `TRANSFER_UPLOAD_SECRET_PREVIOUS` and the new one in `TRANSFER_UPLOAD_SECRET`.
   Deploy and verify an existing server still transfers. Do not empty the primary
   secret or remove the previous secret yet.
5. In Creator Dashboard, update the existing `transfer_upload_secret` secret for
   the legacy universe `210213771` to the new value. Keep its domain restricted
   to `cross-game-data-production.up.railway.app`. The active uploader is
   `ServerScriptService.TransferHandler` in Transfer Test, place `81283042231786`.
   Verify other active uploaders and universes use the same updated credential.
6. Roblox loads secret values when servers start. Existing servers retain the old
   value. Bring up fresh transfer servers, verify intended transfers there, then
   drain/restart old uploader servers in a controlled way. Coordinate any menu
   servers that also upload. Changing a source file or the dashboard alone does
   not refresh secrets in running servers.
7. Once no active uploader needs the old secret, remove
   `TRANSFER_UPLOAD_SECRET_PREVIOUS` from Railway and redeploy. Verify a fresh
   server still transfers and unauthenticated uploads receive `401`.

Keep both values out of chat, source control, screenshots, and logs. Record
deployment IDs and test outcomes, not credential values. Replacing a variable
does not revoke the old Roblox API key; revoke it in Roblox after verification.

References:

- [Railway security disclosure](https://blog.railway.com/p/security-disclosure-wednesday-october-21st)
- [Roblox API key management](https://create.roblox.com/docs/cloud/auth/api-keys)
- [Roblox Secrets Store lifecycle](https://devforum.roblox.com/t/secrets-store-general-availability/2892154/1)
