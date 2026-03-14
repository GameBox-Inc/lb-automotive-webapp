# Create a GitHub App for GHCR (organization: GameBox-Inc)

This walkthrough creates a **GitHub App owned by your organization** so you can use installation access tokens instead of a Personal Access Token (PAT) for pushing images to GHCR. The app is tied to the org, not a user, so it doesn’t depend on one person’s PAT.

**Where to build the JWT / get the token:** Use the script **`deployment/scripts/github_app_token.sh`** in the place that needs the token: **in Jenkins** (before `docker login` and push) and optionally **on the cluster** (e.g. in a CronJob that updates `ghcr-secret`). You don’t build the JWT by hand; the script does it.

---

## Prerequisites (org)

- You must be an **owner** (or have **admin** rights to GitHub App settings) of the **GameBox-Inc** organization.
- The repo and GHCR packages are under **GameBox-Inc** (e.g. `github.com/gamebox-inc/lb-automotive-webapp`, `ghcr.io/gamebox-inc/lb-automotive-backend`).

---

## Part 1: Create the GitHub App (in the org)

1. **Open the org’s GitHub Apps**
   - Go to **https://github.com/organizations/gamebox-inc/settings/apps**
   - Or: **GitHub** → switch to org **GameBox-Inc** (top-left) → **Settings** → in the left sidebar under **Developer settings** → **GitHub Apps**.

2. **Create a new app**
   - Click **New GitHub App**.

3. **Fill in the form (org-specific)**

   | Field | Value |
   |--------|--------|
   | **GitHub App name** | `lb-automotive-ghcr` (must be unique across GitHub; include org or product name). |
   | **Homepage URL** | `https://github.com/gamebox-inc/lb-automotive-webapp` |
   | **Callback URL** | `https://example.com` (not used for machine-only tokens). |
   | **Setup URL** | Leave blank. |
   | **Webhook** | **Uncheck “Active”** (no webhooks needed for GHCR). |
   | **Repository permissions** | |
   | → **Contents** | **Read-only** (or **No access** if you only need Packages). |
   | → **Metadata** | **Read-only** (often default). |
   | → **Packages** | **Read and write**. |
   | **Where can this GitHub App be installed?** | **Only on this account** (so only the GameBox-Inc org can install it). |

4. Click **Create GitHub App**.

5. **Generate a private key**
   - On the app’s page, scroll to **Private keys**.
   - Click **Generate a private key** and download the `.pem` file.
   - Store it securely (e.g. in Jenkins credentials and/or a secret manager). You cannot download it again.

6. **Note these (org app)**
   - **App ID** (e.g. `123456`) — shown on the app’s main page under the app name.
   - **Private key** — the `.pem` you just downloaded.
   - **Installation** — you’ll do this in Part 2; the app will be installed on the **GameBox-Inc** org.

---

## Part 2: Install the App on the organization

1. **Start installation**
   - On the app’s page (you should still be there after creating it), in the left sidebar click **Install App**.

2. **Choose the organization**
   - You’ll see **Install next to “GameBox-Inc”** (or the org you’re in). Click **Install** next to **GameBox-Inc**.

3. **Choose repositories**
   - **All repositories** — app can access every repo in the org (simplest if you have few repos).
   - **Only select repositories** — choose at least `lb-automotive-webapp` (and any other repos whose CI pushes to GHCR). Then click **Install**.

4. **Get the Installation ID**
   - After install you’re on the **installation** page. The URL is:
     - `https://github.com/organizations/gamebox-inc/settings/installations/<INSTALLATION_ID>`
   - Or: **GameBox-Inc** → **Settings** → **Applications** → **Installed GitHub Apps** → **lb-automotive-ghcr** — the Installation ID is in the URL or on that page.
   - Save this **Installation ID** (numeric); you need it to request tokens.

---

## Part 3: Get an installation access token (where to build the JWT)

The app has no “password”. You use the **private key** to sign a JWT, then exchange it for a short-lived **installation access token** (~1 hour).

**Where to build the JWT:** Run the script **in the same place you need the token**:
- **For Jenkins (push to GHCR):** Run the script inside the Jenkins pipeline (agent that runs `docker push`), so every build gets a fresh token, then `docker login` and push.
- **For cluster pull (optional):** Run the script from a CronJob or one-off job on the cluster that updates `ghcr-secret`; the script can live in the repo and be run via a job that has the private key and IDs in a K8s secret.

**Use the script in the repo** (builds the JWT and fetches the token for you):

```bash
# From repo root (e.g. on Jenkins agent or on the server)
chmod +x deployment/scripts/github_app_token.sh
TOKEN=$(deployment/scripts/github_app_token.sh "<APP_ID>" "<INSTALLATION_ID>" "/path/to/your-app.pem")
echo "$TOKEN" | docker login ghcr.io -u "<APP_ID>" --password-stdin
```

Script: **`deployment/scripts/github_app_token.sh`**  
Usage: `./github_app_token.sh <APP_ID> <INSTALLATION_ID> <path-to-.pem>`  
Requires: `openssl`, `curl`, and optionally `jq` (for robust JSON parsing).  
Output: the token on stdout (or non-zero exit and message on stderr).

**Log in to GHCR (org packages)**
- Org packages at `ghcr.io/gamebox-inc/*` accept the installation token when the username is the **App ID**:
```bash
echo "$TOKEN" | docker login ghcr.io -u "<APP_ID>" --password-stdin
docker push ghcr.io/gamebox-inc/lb-automotive-backend:some-tag
```

---

## Part 4: Jenkins credentials (add these; optionally remove the old PAT)

**Add** these credentials in Jenkins so the pipeline can get an installation token and push to GHCR:

| Credential kind   | Credential ID (use these in Jenkinsfile) | What to store |
|-------------------|------------------------------------------|----------------|
| **Secret file**   | `github-app-ghcr-key`                    | The app’s **private key** (`.pem` file you downloaded). Upload as a file. |
| **Secret text**   | `github-app-id`                          | The **App ID** (e.g. `123456`). |
| **Secret text**   | `github-app-installation-id`             | The **Installation ID** (numeric, from the install URL or org’s Installed GitHub Apps). |

**Where to add them:** **Jenkins** → **Manage Jenkins** → **Credentials** → **(your domain, e.g. System → Global)** → **Add Credentials**.

- For the **private key:** Kind = **Secret file**; **File** = Upload, choose the `.pem`; **ID** = `github-app-ghcr-key`; **Description** = e.g. “GitHub App private key for GHCR”.
- For **App ID** and **Installation ID:** Kind = **Secret text**; **Secret** = the numeric value; **ID** = `github-app-id` and `github-app-installation-id` respectively.

**Optional:** You can **remove or stop using** the existing `github-token` (PAT) credential once the pipeline is updated to use the app. Until then, keep it as a fallback if you want.

**Do not add** the installation token itself as a long‑lived credential; the pipeline will generate it from the app key + IDs using `deployment/scripts/github_app_token.sh`.

**Pipeline: use the credentials**

In the Jenkinsfile, replace the existing GHCR login block with one that uses the script and these credential IDs:

```groovy
withCredentials([
    file(credentialsId: 'github-app-ghcr-key', variable: 'GITHUB_APP_KEY'),
    string(credentialsId: 'github-app-id', variable: 'GITHUB_APP_ID'),
    string(credentialsId: 'github-app-installation-id', variable: 'GITHUB_APP_INSTALLATION_ID')
]) {
    sh '''
        TOKEN=$(./deployment/scripts/github_app_token.sh "$GITHUB_APP_ID" "$GITHUB_APP_INSTALLATION_ID" "$GITHUB_APP_KEY")
        echo "$TOKEN" | docker login ghcr.io -u "$GITHUB_APP_ID" --password-stdin
    '''
}
// then your existing docker push commands
```

---

## Part 5: Cluster pull (org packages)

- **Option A — PAT for pull only**
  - Create a PAT (under an org member or a bot account) with `read:packages`, store it only in `ghcr-secret` on the cluster. Don’t use it for Git or Jenkins. Rotate rarely.

- **Option B — Same org app for pull**
  - Store the app’s private key and App ID + Installation ID in a K8s secret. Run a CronJob every ~50 minutes that gets a new installation token and updates `ghcr-secret` (e.g. `kubectl create secret docker-registry ghcr-secret ... --dry-run=client -o yaml | kubectl apply -f -`). Then the cluster pulls `ghcr.io/gamebox-inc/*` using the org app’s token.

---

## Org-specific summary

| Item | Where (GameBox-Inc org) |
|------|--------------------------|
| Create app | **https://github.com/organizations/gamebox-inc/settings/apps** → New GitHub App |
| App permissions | Repository: **Packages** Read and write; **Contents** Read-only or No access |
| Install app | Same app page → **Install App** → Install on **GameBox-Inc** → choose repos |
| Installation ID | **Settings** → **Applications** → **Installed GitHub Apps** → app → URL or page |
| Packages | Pushed/pulled as `ghcr.io/gamebox-inc/<image>:<tag>`; token from app works for both push (CI) and pull (cluster) |

After this, GHCR auth is tied to the **organization** app, not a personal PAT, so configuring Git on a MacBook or rotating a user token won’t break image push or pull.
