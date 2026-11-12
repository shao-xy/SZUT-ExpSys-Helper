"""密码加密：复刻站点前端 JsAESEncrypt。

站点在提交前用 CryptoJS 的 AES-CBC 加密密码，密钥与 IV 相同。
"""

from __future__ import annotations

import base64

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

AES_KEY = b"Easyman-easyman3"
AES_IV = b"Easyman-easyman3"


def encrypt_password(plain: str) -> str:
    """将明文密码加密为 Base64 字符串。"""
    cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_IV)
    ciphertext = cipher.encrypt(pad(plain.encode("utf-8"), AES.block_size, style="pkcs7"))
    return base64.b64encode(ciphertext).decode("utf-8")


def decrypt_password(ciphertext_b64: str) -> str:
    """解密 Base64 字符串，用于读取本地加密凭据文件。"""
    cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_IV)
    padded = cipher.decrypt(base64.b64decode(ciphertext_b64))
    return unpad(padded, AES.block_size, style="pkcs7").decode("utf-8")
