from pywebtransport.utils import generate_self_signed_cert
print("Generating new short-lived certificate for 127.0.0.1...")
generate_self_signed_cert(hostname="127.0.0.1", validity_days=10)
print("Done.")