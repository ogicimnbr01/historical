import zipfile
import sys

zip_path = r"c:\tokmak\broje\shorts\historical\lambda\layer\python-google.zip"

try:
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        files = zip_ref.namelist()
        print(f"Total files: {len(files)}")
        
        # Check for googleapiclient
        google_files = [f for f in files if "googleapiclient" in f]
        print(f"Files containing 'googleapiclient': {len(google_files)}")
        
        if len(google_files) > 0:
            print("First 5 googleapiclient files:")
            for f in google_files[:5]:
                print(f" - {f}")
        else:
            print("WARNING: No googleapiclient files found!")
            
        # Check for google-auth
        auth_files = [f for f in files if "google/auth" in f]
        print(f"Files containing 'google/auth': {len(auth_files)}")
        
        if len(auth_files) > 0:
            print("First 5 google/auth files:")
            for f in auth_files[:5]:
                print(f" - {f}")
        else:
            print("WARNING: No google-auth files found!")
            
        # Check for protobuf
        proto_files = [f for f in files if "google/protobuf" in f]
        print(f"Files containing 'google/protobuf': {len(proto_files)}")
        
        if len(proto_files) > 0:
            print("First 5 google/protobuf files:")
            for f in proto_files[:5]:
                print(f" - {f}")

        # Check for .so or .pyd files (binary extensions)
        binary_files = [f for f in files if f.endswith(".so") or f.endswith(".pyd")]
        print(f"Binary extensions (.so/.pyd): {len(binary_files)}")
        if len(binary_files) > 0:
            print("First 5 binary files:")
            for f in binary_files[:5]:
                 print(f" - {f}")

except Exception as e:
    print(f"Error reading zip: {e}")
