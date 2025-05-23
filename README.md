```markdown
# GitHub AUR Updater (gh-aur-updater)

`gh-aur-updater` is a Python application designed to automate the process of updating Arch Linux packages maintained on the AUR. It monitors upstream sources for new versions, updates PKGBUILDs, builds packages in a clean environment, pushes changes to the AUR, and manages GitHub releases.

This tool is intended to be run in a CI/CD environment, particularly GitHub Actions, to keep your AUR packages up-to-date with minimal manual intervention.

## Features

*   **Python-centric:** Core logic written in Python for better maintainability and testability.
*   **PKGBUILD Parsing:** Uses `makepkg --printsrcinfo` for robust metadata extraction from PKGBUILDs.
*   **Upstream Version Checking:** Leverages `nvchecker` to detect new upstream versions.
*   **AUR Interaction:** Clones AUR repositories, commits, and pushes changes.
*   **GitHub Release Management:**
    *   Deletes existing releases/tags for a package version to ensure only the latest build is available.
    *   Creates new GitHub releases with built package assets.
*   **Source Repository Sync:** Updates PKGBUILD and .SRCINFO files in your source GitHub repository after a successful AUR update.
*   **Configurable:** Uses environment variables for flexible configuration in CI environments.
*   **GitHub Actions Logging:** Provides clear, formatted log output for GitHub Actions.
*   **Dry Run Mode:** Allows testing the workflow without making any actual changes to AUR or GitHub.

## Installation & Setup

This project is designed to be run from```markdown source within a CI environment, but can also be installed locally for development or testing.

1.  **Prerequisites:**
    
# GitHub AUR Updater (gh-aur-updater)

`gh-aur-updater` is a Python-based automation tool designed to streamline the process of updating Arch Linux packages maintained on the AUR.*   Python 3.9+
    *   Git
    *   `gh` (GitHub CLI) - Authenticated
    *   `makepkg` and related Arch Linux build tools (e.g., `devtools It integrates with GitHub Actions to monitor upstream changes, update PKGBUILDs, build packages, manage AUR repository pushes, and handle` package)
    *   `nvchecker`
    *   An SSH key configured for pushing to AUR (e.g GitHub Releases.

This tool has evolved from a series of shell scripts into a more robust and maintainable Python package, leveraging., `~/.ssh/id_rsa` for the user running the script, with the public key added to your AUR account).

2.  **Clone the repository (if running from source):**
    ```bash
    git clone https modern Python practices and tooling.

## Features

*   **Automated Upstream Version Checking:** Uses `nvchecker` to monitor upstream sources for new versions.
*   **PKGBUILD Metadata Parsing:** Safely parses PKGBUILDs://github.com/your-username/gh-aur-updater.git
    cd gh-aur-updater
     by generating and reading `.SRCINFO` files.
*   **AUR Package Management:**
    *   Clones existing```

3.  **Create a Virtual Environment (Recommended):**
    ```bash
    python -m venv .venv
    source .venv/bin/activate  # Linux/macOS
    # .venv\Scripts\activate    # Windows
    ```

4.  **Install Dependencies:**
    The project uses `py AUR repositories for packages.
    *   Updates PKGBUILDs with new versions and resets `pkgrel`.
    *   Automatically runs `updpkgsums` and regenerates `.SRCINFO`.
    *   Commits changesproject.toml`.
    ```bash
    python -m pip install --upgrade pip
    pip install .[dev] # Installs runtime and development/test dependencies
    ```
    For runtime only (e.g., in a minimal CI):
    ```bash
    pip install .
    ```

## Usage

Once installed (or if running from a properly to the local AUR git clone and pushes to the AUR.
*   **Package Building:** Uses `makepkg` to build packages in a clean environment.
*   **GitHub Release Management:**
    *   Deletes and recreates set up source tree with dependencies installed), the application is executed via the `gh-aur-updater` command:

```bash
 GitHub releases and associated tags to ensure only the latest build for a version is present.
    *   Uploads built package artifacts (`*.pkg.tar.zst`) to GitHub Releases.
*   **Source Repository Sync:** Updatesgh-aur-updater
```

The behavior of the script is controlled entirely by environment variables.

## Configuration ( PKGBUILD and `.SRCINFO` files back in your source GitHub repository.
*   **Configurable:**Environment Variables)

The following environment variables are used to configure `gh-aur-updater`:

### Required Variables:

*   **`GITHUB_REPOSITORY`**: The owner and repository name (e.g., `yourusername/your Behavior is controlled via environment variables, suitable for CI/CD environments like GitHub Actions.
*   **GitHub Actions Optimized Logging:** Provides clear, formatted log output for GitHub Actions.
*   **Dry Run Mode:** Allows testing the workflow without making any-repo`).
    *   Provided automatically by GitHub Actions.
*   **`GH_TOKEN`**: A actual changes to AUR or GitHub.

## Installation (for Development/Contribution)

This project uses Python 3.9 GitHub token with permissions to read repository contents, manage releases, and write to the repository (for syncing PKGBUILDs+ and `pyproject.toml` for packaging.

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your_username/gh-aur-updater.git # Replace with your repo).
    *   Typically `secrets.GITHUB_TOKEN` in GitHub Actions.
*   **`GITHUB_WORKSPACE URL
    cd gh-aur-updater
    ```

2.  **Create and activate a virtual environment:**`**: The absolute path to the directory where the repository has been checked out.
    *   Provided automatically by GitHub Actions.
*   **`AUR_MAINTAINER_NAME`**: Your AUR username. Used to identify packages you
    ```bash
    python -m venv .venv
    source .venv/bin/activate  # Linux maintain.

### Optional Variables (with defaults):

*   **`GITHUB_RUNID`**: The unique ID/macOS
    # .venv\Scripts\activate    # Windows
    ```

3.  **Install in editable mode with development dependencies:**
    ```bash
    pip install --upgrade pip
    pip install -e . of the GitHub Actions run.
    *   Default: `local-run-unknown-id` (if not in[dev]
    ```
    The `[dev]` extra includes dependencies for testing and development tools like `pytest`, `black GHA).
    *   Provided automatically by GitHub Actions.
*   **`GITHUB_ACTOR`**: The username of the user who initiated the workflow.
    *   Default: `github-actions[bot]`.
    *   Provided automatically by GitHub Actions.
*   **`AUR_GIT_USER_NAME`**: The name to`, `ruff`, etc.

## Usage

Once installed (e.g., in editable mode or via `pip install use for Git commits to the AUR.
    *   Default: Value of `AUR_MAINTAINER_NAME`.
*   **`AUR_GIT_USER_EMAIL`**: The email to use for Git commits to the AUR. .`), the tool is run using the command-line entry point:

```bash
gh-aur-updater
```

This command should typically be executed within a GitHub Actions workflow environment where all necessary environment variables are set.

### GitHub Actions Workflow Example

```yaml
name: Update AUR Packages

on:
  workflow_dispatch: # Manual
    *   Default: `{AUR_MAINTAINER_NAME_LOWERCASED_AND_HYPHENATED}@users.noreply.github.com` or `{GITHUB_ACTOR}@users.noreply.github.com`.
*   **`SOURCE_REPO_GIT_USER_NAME`**: The name to use for Git commits when trigger
  schedule:
    - cron: '0 4 * * *' # Example: Run daily at 4 syncing PKGBUILDs back to your source GitHub repository.
    *   Default: `"{GITHUB_ACTOR} ( AM UTC

jobs:
  update_aur_packages:
    runs-on: ubuntu-latest # Or your preferredvia CI)"`.
*   **`SOURCE_REPO_GIT_USER_EMAIL`**: The email for source repository Arch Linux based runner
    permissions:
      contents: write  # To push to source repo and create releases
      # commits.
    *   Default: `{GITHUB_ACTOR}@users.noreply.github.com`.
*   **`PACKAGE_BUILD_BASE_DIR`**: Base directory where package-specific temporary build directories will be created.
     id-token: write # If using OIDC for gh auth, not needed for GH_TOKEN
    steps:
      *   Default: `$HOME/arch_package_builds` (or `/tmp/arch_package_builds` if- name: Checkout Repository
        uses: actions/checkout@v4
        with:
          # Using a PAT `HOME` is not set).
*   **`NVCHECKER_RUN_DIR`**: Directory for global `nvchecker` files (e.g., `aur.json`, aggregated `new.toml`, `keyfile. with repo and workflow scopes if pushing to source repo from action
          # Otherwise, GITHUB_TOKEN might be sufficient for releasestoml`).
    *   Default: `$HOME/nvchecker_run` (or `/tmp/nvchecker_ if settings allow
          token: ${{ secrets.YOUR_FINE_GRAINED_PAT_OR_CLASSIC_PAT_WITH_REPO_SCOPE }}


      - name: Set up Python
        uses: actions/setup-python@vrun` if `HOME` is not set).
*   **`ARTIFACTS_DIR`**: Base directory where build artifacts (logs, built packages) for each package will be stored in subdirectories.
    *   Default5
        with:
          python-version: '3.11' # Or your preferred Python version

      - name: Install Dependencies
        run: |
          python -m pip install --upgrade pip
          pip install: `${GITHUB_WORKSPACE}/artifacts`.
*   **`COMMIT_MESSAGE_PREFIX`**: Prefix for automated commit messages.
 -e .[dev] # Installs the updater and its dependencies

      - name: Configure Git for AUR Comm    *   Default: `CI: Auto update`.
*   **`DEBUG_MODE`**: Set to `true`, `1`, or `yes` to enable debug logging.
    *   Default: `false`.
its
        run: |
          # This configures git globally in the runner for the AUR maintainer identity
          #*   **`DRY_RUN_MODE`**: Set to `true`, `1`, or `yes Alternatively, the Python script can configure this per-repo if needed
          git config --global user.name "${{ env` to prevent any actual changes (no git pushes, no GitHub releases/file modifications). Actions will be logged as if they were.AUR_MAINTAINER_NAME }}" # Or a specific bot name
          git config --global user.email "${{ env.AUR_MAINTAINER_EMAIL }}" # Or a specific bot email

      - name: Run performed.
    *   Default: `false`.
*   **`SECRET_GHUK_VALUE`**: Your GitHub token specifically for `nvchecker` to access private repositories or increase API rate limits (if needed for version checking some GitHub AUR Updater
        env:
          # Required Secrets & Variables
          GH_TOKEN: ${{ secrets.YOUR_FINE_GRAINED_PAT_OR_CLASSIC_PAT_WITH_REPO_SCOPE }} # Needs repo scope for releases sources). This will be written to `keyfile.toml` for `nvchecker`.
    *   Default: Not set (keyfile will not be generated).

### Example GitHub Actions Workflow Snippet:

```yaml
name: Update and source repo updates
          AUR_MAINTAINER_NAME: "your_aur_username"
          SECRET AUR Packages

on:
  schedule:
    - cron: '0 4 * * *' # Example_GHUK_VALUE: ${{ secrets.NVCHECKER_GITHUB_TOKEN }} # Optional: GitHub token for nvchecker rate: Run daily at 4 AM UTC
  workflow_dispatch: # Allow manual triggering

jobs:
  update limiting

          # GitHub Provided (usually automatic, but good to be aware)
          GITHUB_REPOSITORY: ${{ github.repository }}
          GITHUB_WORKSPACE: ${{ github.workspace }}
          GITHUB_RUNID: ${{ github.run_id_aur_packages:
    runs-on: ubuntu-latest # Or a custom Arch Linux based runner
    container }}
          GITHUB_ACTOR: ${{ github.actor }}

          # Optional: Override Git committer details if: # Example: Use an Arch Linux container with necessary tools
      image: archlinux:latest # Or your custom different from global git config
          # AUR_GIT_USER_NAME: "Your AUR Commit Bot Name"
          # AUR_GIT_USER_EMAIL: "bot-email@example.com"
          # SOURCE_REPO Docker image
      options: --user root # Or a user with sudo access for package installation

    steps:
      - name: Checkout Repository
        uses: actions/checkout@v4
        with:
          # Fetch full history if_GIT_USER_NAME: "Source Repo Update Bot"
          # SOURCE_REPO_GIT_USER_EMAIL: "source-bot-email@example.com"
          
          # Optional: Behavior flags
          DEBUG_ your nvchecker or other tools need it
          # fetch-depth: 0 
          # Token for checkoutMODE: "false" # Set to "true" for verbose debug logging
          DRY_RUN_MODE: "false if you need to push back to this repo and default token lacks perms
          # token: ${{ secrets.PAT" # Set to "true" to simulate without making changes

          # Optional: Path overrides (defaults are usually fine within_FOR_SOURCE_REPO_SYNC }} 

      - name: Set up Python
        uses: actions/setup GHA)
          # PACKAGE_BUILD_BASE_DIR: "${{ github.workspace }}/custom_builds-python@v5
        with:
          python-version: '3.11' # Or your"
          # NVCHECKER_RUN_DIR: "${{ github.workspace }}/custom_nvchecker_run"
          # ARTIFACTS_DIR: "${{ github.workspace }}/custom_artifacts"
        run: |
          gh-aur-updater

      # Optional: Upload artifacts if your script places them in desired Python version

      - name: Prepare Arch Environment (if using a generic runner)
        if: runner.os a known location
      # - name: Upload Build Artifacts
      #   uses: actions/upload-artifact@v3 == 'Linux' && steps.container-check.outputs.is_arch != 'true' # Example condition
        run:
      #   if: always() # Run even if previous steps fail, to get logs
      #   with:
 |
          sudo pacman -Syu --noconfirm
          sudo pacman -S --needed --noconfirm git base-devel devtools nvchecker github-cli
          # Configure SSH for AUR access (e.g., by      #     name: build-artifacts-${{ github.run_id }}
      #     path: ${{ github.workspace }}/artifacts/ # Or your config.artifacts_dir_base
```
**Note on SSH for AUR:** P writing secrets.AUR_SSH_KEY to ~/.ssh/id_rsa)
          # mkdir -p ~/.ssh && chmodushing to AUR via SSH (`ssh://aur@aur.archlinux.org/...`) requires the runner to have an 700 ~/.ssh
          # echo "${{ secrets.AUR_SSH_PRIVATE_KEY }}" > ~/.ssh/id_rsa
          # chmod 600 ~/.ssh/id_rsa
          # ssh-keyscan aur SSH key configured that is authorized for your AUR account. GitHub Actions workflows can be configured with SSH keys using secrets.

## Configuration (.archlinux.org >> ~/.ssh/known_hosts
          # Configure git for AUR (might be overridden by theEnvironment Variables)

The `gh-aur-updater` is configured entirely through environment variables. These are typically set in script if specific AUR_GIT vars are set)
          # git config --global user.name "${{ env.AUR_MAINTAINER_NAME }}"
          # git config --global user.email "${{ env.AUR_MAINTAIN your GitHub Actions workflow file.

### Required Variables:

*   `GH_TOKEN`: A GitHub Personal Access TokenER_NAME }}@users.noreply.github.com"


      - name: Install Python Dependencies
        run (PAT) with `repo` scope (for creating releases, updating files in your source repository) and potentially `workflow: |
          python -m pip install --upgrade pip
          pip install .[dev] # Or just '` scope (if modifying workflows, though not typical for this tool). **Important:** Use a fine-grained PAT ifpip install .' for runtime

      - name: Run gh-aur-updater
        env:
          GH_TOKEN: ${{ possible, limited to the specific repositories.
*   `AUR_MAINTAINER_NAME`: Your username on secrets.GITHUB_TOKEN }}
          AUR_MAINTAINER_NAME: "YourAURUsername" # Replace or the Arch User Repository.
*   `GITHUB_REPOSITORY`: (Provided by GitHub Actions) The owner and repository name ( use secrets/env
          SECRET_GHUK_VALUE: ${{ secrets.YOUR_NVCHECKER_GITHUB_TOKEN }} #e.g., `username/my-aur-packages`).
*   `GITHUB_WORKSPACE`: (Provided by Optional
          # GITHUB_* variables are automatically set by Actions
          DEBUG_MODE: "false" 
          DR GitHub Actions) The path to the directory on the runner where your repository is checked out.

### Optional Variables:

*   `SECRET_GHUK_VALUE`: A GitHub token specifically for `nvchecker` to use (passed to `keyY_RUN_MODE: "false" # Set to true for testing
          # Optional: Override git committer details if needed
          # AUR_GIT_USER_NAME: "AUR Commit Bot"
          # AUR_GIT_USER_EMAILfile.toml`). This helps with GitHub API rate limits when checking for updates on GitHub-hosted sources.
*   : "bot@example.com"
        run: |
          gh-aur-updater

      # Optional: Upload artifacts (logs, packages)
      - name: Upload Build Artifacts
        if: always() # Run`GITHUB_RUNID`: (Provided by GitHub Actions) A unique ID for the workflow run.
*   `GITHUB_ACTOR`: (Provided by GitHub Actions) The username of the person or bot that initiated the workflow.
*   `AUR even if previous steps fail, to get logs
        uses: actions/upload-artifact@v4
        with_GIT_USER_NAME`: Name to use for commits to AUR repositories.
    *   Default: Value of `AUR_:
          name: gh-aur-updater-artifacts-${{ github.run_id }}
          path: ${{ githubMAINTAINER_NAME`.
*   `AUR_GIT_USER_EMAIL`: Email to use for commits to AUR repositories.
    *   Default: Constructed from `AUR_GIT_USER_NAME` or `AUR.workspace }}/artifacts/ # Path set by ARTIFACTS_DIR default
```

## Project Structure

(A brief overview of the Python module structure could be added here if desired, but might be too detailed for a primary README).

*_MAINTAINER_NAME` (e.g., `username@users.noreply.github.com`).
*   `SOURCE_REPO_GIT_USER_NAME`: Name to use for commits back to your source GitHub repository (   `main.py`: Main orchestrator script.
*   `config.py`: Handles loading of `BuildConfiguration`.when syncing PKGBUILD/.SRCINFO).
    *   Default: Constructed from `GITHUB_ACTOR
*   `models.py`: Core data classes (e.g., `PKGBUILDData`, `AUR` (e.g., `github_actor (via CI)`).
*   `SOURCE_REPO_GIT_USER_PackageInfo`).
*   `logging_utils.py`: Configures logging for GitHub Actions.
*   EMAIL`: Email for source repository commits.
    *   Default: Constructed from `GITHUB_ACTOR` (e.g`pkgbuild_parser.py`: Parses PKGBUILDs using `.SRCINFO`.
*   `workspace_scanner.py`: Finds PKGBUILDs in the workspace.
*   `aur_client.py`: Inter., `github_actor@users.noreply.github.com`).
*   `COMMIT_MESSAGE_PREFIX`: Prefix for automated commit messages.
    *   Default: `CI: Auto update`
*   `DEBUG_MODEacts with AUR RPC.
*   `nvchecker_client.py`: Wraps `nvchecker` CLI.
*   `: Set to `"true"` to enable verbose debug logging.
    *   Default: `"false"`
*   `github_client.py`: Interacts with GitHub API via `gh` CLI.
*   `package_updater.py`: Handles the update, build, and publish cycle for a single package.
*   `utils.py`DRY_RUN_MODE`: Set to `"true"` to simulate all operations without making actual changes (no git pushes, no`: Common utilities like the subprocess runner.
*   `exceptions.py`: Custom application exceptions.

## Contributing

Contributions are welcome GitHub API writes).
    *   Default: `"false"`
*   `PACKAGE_BUILD_BASE_DIR`: Override! Please feel free to submit issues or pull requests. For major changes, please open an issue first to discuss what you would the base directory for temporary package builds.
    *   Default: `$HOME/arch_package_builds` (where `$HOME` is the home directory of the runner user).
*   `NVCHECKER_RUN_DIR`: Override the directory for global `nvchecker` files (e.g., `aur.json`, `keyfile. like to change.

Ensure any contributions adhere to the existing coding style and include tests where appropriate.

## License

This project istoml`).
    *   Default: `$HOME/nvchecker_run`.
*   `ARTIFACTS_ licensed under the MIT License - see the `LICENSE` file for details (assuming you'll add one).
```

**DIR`: Override the base directory where build artifacts (logs, built packages) for each package will be stored.
    *   DefaultKey things to customize in this README:**

*   **`your-username/gh-aur-updater`**: Replace with: `${GITHUB_WORKSPACE}/artifacts`.

## Project Structure

*   `arch_package_updater/`: Main your actual GitHub repository URL.
*   **`YourAURUsername`**: Replace with actual placeholder or instructions.
*   ** Python package source code.
    *   `main.py`: Main orchestrator and CLI entry point.
    *   `secrets.YOUR_NVCHECKER_GITHUB_TOKEN`**: Update placeholder.
*   **License:** If`config.py`: Loads `BuildConfiguration` from environment variables.
    *   `models.py`: Defines core data structures (dataclasses).
    *   `logging_utils.py`: Configures GitHub Actions-friendly logging.
     you choose a different license, update the license field in `pyproject.toml` and the "License" section in*   `pkgbuild_parser.py`: Parses PKGBUILDs via `.SRCINFO`.
    * the README. Make sure to add a `LICENSE` file to your repository.
*   **Prerequisites/Environment Setup:** Adjust the "Prepare Arch Environment" step in the example workflow based on whether you're using a generic Ubuntu   `workspace_scanner.py`: Finds PKGBUILDs in the workspace.
    *   `aur_client.py`: Interacts with AUR RPC.
    *   `github_client.py`: Interacts with GitHub API via `gh` CLI.
    *   `nvchecker_client.py`: Wraps `nvchecker` and runner (requiring `pacman` setup) or a dedicated Arch Linux runner/container. The SSH key setup for AUR is critical.
*   **Project Structure (Optional Detail):** You can expand or simplify the "Project Structure" section `nvcmp`.
    *   `package_updater.py`: Core logic for processing/building/publishing.

This README provides a good starting point for users and contributors to understand, configure, and use your `gh-aur-updater` project.
