# PyInstaller: đóng gói SUpload thành thư mục dist/SUpload/ (SUpload.exe + thư viện).
#   pyinstaller packaging/supload.spec --noconfirm
# Dạng thư mục (onedir) khởi động nhanh hơn và ít bị phần mềm diệt virus báo nhầm hơn dạng 1 file.
import os
from PyInstaller.utils.hooks import collect_submodules

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))

a = Analysis(
    [os.path.join(ROOT, "packaging", "launcher.py")],
    pathex=[ROOT],
    datas=[(os.path.join(ROOT, "web"), "web")],          # giao diện đã build
    hiddenimports=collect_submodules("supload"),          # blueprint được import động
    # cách Trình duyệt (playwright) không đóng gói; các thư viện lớn còn lại ứng dụng không dùng
    excludes=["playwright", "tkinter", "pytest", "numpy", "PIL", "lxml", "yaml", "cryptography", "pandas", "matplotlib"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="SUpload",
    console=True,     # cửa sổ dòng lệnh để xem trạng thái / Ctrl+C; tự khởi động cùng Windows thì chạy ẩn
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="SUpload", upx=False)
