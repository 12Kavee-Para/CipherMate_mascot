# Record a two-minute CipherMate file demo

Use a local offline demo workspace. Choose fresh filenames and a fresh key label if this demo has already been recorded. Start the app from the project directory with `bash scripts/run_local.sh` and open http://127.0.0.1:8000/.

| Time | Show on screen | Say |
|---|---|---|
| 0:00–0:15 | Create a plain-text file named `demo-note.txt`. Type `The greenhouse opens at nine.` and save it. | “Here’s the file we’ll protect. At the end, we’ll check that we recovered these exact bytes.” |
| 0:15–0:35 | In CipherMate, open **Workspace tools → Files**. Choose the file, leave the optional path blank, and click **Upload**. Send `hash demo-note.txt` in chat and keep the returned SHA-256 digest on screen. | “The file is in my workspace. This fingerprint gives me a reference to check after decryption.” |
| 0:35–0:50 | Send `create key fernet demo-key`. Review the label, click **Approve operation**, and confirm. | “CipherMate generates a key in my vault. I can refer to it by its label without displaying the secret.” |
| 0:50–1:15 | Send `encrypt demo-note.txt to demo-note.cm using demo-key`. Pause on the source and destination. Approve and confirm. Wait for **Completed**. | “I’m authorizing a separate encrypted file. My original stays available.” |
| 1:15–1:40 | Send `decrypt demo-note.cm to recovered-note.txt using demo-key`. Review, approve, and confirm. | “Recovery uses the same vault key. I’m writing the result under a new name.” |
| 1:40–2:00 | Send `compare recovered-note.txt to DIGEST`, replacing DIGEST with the original 64-character fingerprint. Show the true result. Open **Workspace tools → Files**, download `recovered-note.txt` by exact path, and open it. | “The fingerprints match. Here’s the downloaded file, with the same sentence we started with.” |
