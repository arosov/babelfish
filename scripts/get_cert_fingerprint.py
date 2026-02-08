import subprocess
import os
import hashlib
import sys

def get_fingerprint(cert_path: str):
    if not os.path.exists(cert_path):
        print(f"Error: {cert_path} not found.")
        return
    
    # Run openssl to get the DER format of the cert
    cmd = ["openssl", "x509", "-in", cert_path, "-outform", "der"]
    try:
        der_data = subprocess.check_output(cmd)
    except subprocess.CalledProcessError as e:
        print(f"Error running openssl: {e}")
        return
    
    sha256_hash = hashlib.sha256(der_data).hexdigest()
    
    # Format as colon-separated hex pairs
    formatted = ":".join(sha256_hash[i:i+2] for i in range(0, len(sha256_hash), 2))
    
    print("\n" + "="*60)
    print("      WEBTRANSPORT CERTIFICATE FINGERPRINT (SHA-256)")
    print("="*60)
    print(f"File: {cert_path}")
    print(f"Raw Hex: {sha256_hash}")
    print(f"Colon Format: {formatted}")
    print("="*60)

if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1.crt"
    get_fingerprint(path)
