# Installation Guide for Terratest Suite

## Quick Start

If Go is already installed on your system:

```bash
cd test
go mod download
go mod verify
```

If you encounter errors, follow the platform-specific guide below.

---

## Platform-Specific Installation

### Windows

#### 1. Install Go

**Option A: Using Official Installer (Recommended)**
1. Download Go 1.21+ from https://go.dev/dl/go1.21.6.windows-amd64.msi
2. Run the installer (will install to `C:\Program Files\Go`)
3. Verify installation by opening a NEW PowerShell window:
   ```powershell
   go version
   ```

**Option B: Using Chocolatey**
```powershell
choco install golang
```

#### 2. Generate go.sum

After installing Go, run the helper script:

**PowerShell:**
```powershell
cd test
.\generate-go-sum.ps1
```

**Git Bash:**
```bash
cd test
./generate-go-sum.sh
```

---

### macOS

#### 1. Install Go

**Option A: Using Homebrew (Recommended)**
```bash
brew install go
```

**Option B: Using Official Installer**
1. Download from https://go.dev/dl/go1.21.6.darwin-amd64.pkg
2. Run the installer
3. Verify: `go version`

#### 2. Generate go.sum

```bash
cd test
./generate-go-sum.sh
```

---

### Linux (Ubuntu/Debian)

#### 1. Install Go

```bash
# Download Go 1.21
wget https://go.dev/dl/go1.21.6.linux-amd64.tar.gz

# Extract to /usr/local
sudo rm -rf /usr/local/go
sudo tar -C /usr/local -xzf go1.21.6.linux-amd64.tar.gz

# Add to PATH (add to ~/.bashrc or ~/.profile for persistence)
export PATH=$PATH:/usr/local/go/bin

# Verify
go version
```

#### 2. Generate go.sum

```bash
cd test
./generate-go-sum.sh
```

---

## Troubleshooting

### "go: command not found"

**Cause:** Go is not installed or not in your PATH.

**Solution:**
1. Verify Go installation location:
   - Windows: `C:\Program Files\Go\bin\go.exe`
   - macOS: `/usr/local/go/bin/go`
   - Linux: `/usr/local/go/bin/go`

2. Add Go to PATH:

   **Windows (PowerShell - Temporary):**
   ```powershell
   $env:Path += ";C:\Program Files\Go\bin"
   ```

   **Windows (System Environment - Permanent):**
   1. Search "Environment Variables" in Start Menu
   2. Edit "Path" under System Variables
   3. Add: `C:\Program Files\Go\bin`
   4. Restart terminal

   **macOS/Linux (Temporary):**
   ```bash
   export PATH=$PATH:/usr/local/go/bin
   ```

   **macOS/Linux (Permanent):**
   ```bash
   echo 'export PATH=$PATH:/usr/local/go/bin' >> ~/.bashrc
   source ~/.bashrc
   ```

### "go.sum: no such file or directory"

**Cause:** Dependencies not downloaded yet.

**Solution:**
Run the helper script to automatically generate it:
```bash
./generate-go-sum.sh   # Linux/macOS/Git Bash
.\generate-go-sum.ps1  # Windows PowerShell
```

### "module verification failed"

**Cause:** Corrupted module cache.

**Solution:**
```bash
# Clear module cache
go clean -modcache

# Re-download
cd test
go mod download
go mod verify
```

---

## Verification

After setup, verify everything works:

```bash
# Check Go is accessible
go version

# Check dependencies are downloaded
cd test
go list -m all

# Verify go.sum exists
ls go.sum

# Compile tests (doesn't run them)
go test -c
```

Expected output:
- Go version 1.21 or higher
- List of ~50+ dependencies
- `go.sum` file present
- `terraform_aws_sp_autopilot_test.test` binary created

---

## Next Steps

Once installation is complete:

1. **Configure AWS Credentials** - See [README.md](README.md#aws-credentials-configuration)
2. **Run Tests** - See [README.md](README.md#running-tests-locally)
3. **CI/CD Setup** - See [README.md](README.md#cicd-integration)

---

## Dependencies Installed

Running `go mod download` installs:

### Direct Dependencies
- `github.com/gruntwork-io/terratest` v0.46.8 - Terraform testing framework
- `github.com/stretchr/testify` v1.8.4 - Test assertions and mocking

### Transitive Dependencies (~50+ modules including)
- AWS SDK for Go - AWS service interactions
- Terraform JSON library - Parse Terraform outputs
- Docker SDK - Container testing (if needed)
- Kubernetes client - K8s testing (if needed)
- Various cloud provider SDKs (GCP, Azure, etc.)

**Total Download Size:** ~200-300 MB
**Disk Space Required:** ~500 MB (including cache)

---

## Support

If you continue to experience issues:

1. Check [README.md Troubleshooting](README.md#troubleshooting)
2. Verify minimum versions: Go 1.21+, Terraform 1.6.0+
3. Ensure internet connectivity for module download
4. Check disk space (500+ MB free required)
