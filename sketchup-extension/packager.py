import zipfile
import os

# --- ตั้งค่าตรงนี้ ---
PLUGIN_NAME = "go_struct_analysis" # ชื่อไฟล์ Loader (ไม่ต้องใส่ .rb)
VERSION = "1.0.0"
# ------------------

def create_rbz():
    base_dir = os.getcwd()
    loader_file = f"{PLUGIN_NAME}.rb"
    ext_folder = PLUGIN_NAME
    output_file = f"{PLUGIN_NAME}_v{VERSION}.rbz"
    
    print(f"📦 Packaging: {output_file}")
    
    with zipfile.ZipFile(output_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
        # 1. ใส่ Loader File
        if os.path.exists(loader_file):
            print(f" + Root: {loader_file}")
            zipf.write(loader_file, arcname=loader_file)
        else:
            print(f"❌ Error: ไม่พบไฟล์ {loader_file}")
            return
            
        # 2. ใส่ Folder และไฟล์ข้างใน
        if os.path.exists(ext_folder):
            for root, dirs, files in os.walk(ext_folder):
                for file in files:
                    abs_path = os.path.join(root, file)
                    # สร้าง relative path เพื่อไม่ให้ติดชื่อ Drive ไป
                    rel_path = os.path.relpath(abs_path, base_dir)
                    
                    # กรองไฟล์ขยะ
                    if file.startswith(".") or file.endswith(".rbz") or file.endswith(".py") or file.endswith(".zip") or file.endswith(".git"):
                        continue
                        
                    # กรอง Folder ที่ไม่จำเป็น (เช่น .git)
                    if ".git" in rel_path.split(os.sep):
                        continue
                        
                    print(f" + File: {rel_path}")
                    zipf.write(abs_path, arcname=rel_path)
        else:
            print(f"❌ Error: ไม่พบโฟลเดอร์ {ext_folder}")
            return
    
    print("✅ เสร็จสมบูรณ์! พร้อมอัพโหลด")

if __name__ == "__main__":
    create_rbz()
