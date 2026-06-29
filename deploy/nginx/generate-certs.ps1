#Requires -Version 5.1
# Генерация self-signed сертификата для dev HTTPS
$CertDir = Join-Path $PSScriptRoot "certs"
New-Item -ItemType Directory -Force -Path $CertDir | Out-Null

$key = Join-Path $CertDir "key.pem"
$cert = Join-Path $CertDir "cert.pem"

if (Get-Command openssl -ErrorAction SilentlyContinue) {
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 `
        -keyout $key -out $cert `
        -subj "/CN=localhost/O=Railway/C=RU"
    Write-Host "Сертификаты созданы: $CertDir" -ForegroundColor Green
} else {
    Write-Warning "openssl не найден. Установите Git for Windows или OpenSSL."
}
