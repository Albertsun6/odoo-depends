"""
云存储模块 - 支持 Vercel Blob 和本地存储
"""
import os
import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, asdict
import tempfile
import shutil


@dataclass
class AnalysisRecord:
    """分析记录"""
    id: str
    filename: str
    upload_time: str
    file_url: Optional[str]  # 云端 ZIP 文件 URL
    file_size: int
    modules_count: int
    analysis_result: Dict[str, Any]
    
    def to_dict(self) -> Dict:
        return asdict(self)


class CloudStorage:
    """云存储抽象基类"""
    
    def upload_file(self, filename: str, data: bytes) -> str:
        """上传文件，返回 URL"""
        raise NotImplementedError
    
    def download_file(self, url: str) -> bytes:
        """下载文件"""
        raise NotImplementedError
    
    def delete_file(self, url: str) -> bool:
        """删除文件"""
        raise NotImplementedError
    
    def save_record(self, record: AnalysisRecord) -> bool:
        """保存分析记录"""
        raise NotImplementedError
    
    def get_records(self) -> List[AnalysisRecord]:
        """获取所有分析记录"""
        raise NotImplementedError
    
    def get_record(self, record_id: str) -> Optional[AnalysisRecord]:
        """获取单个分析记录"""
        raise NotImplementedError
    
    def delete_record(self, record_id: str) -> bool:
        """删除分析记录"""
        raise NotImplementedError


class VercelBlobStorage(CloudStorage):
    """Vercel Blob 存储实现"""
    
    def __init__(self):
        self.token = os.environ.get('BLOB_READ_WRITE_TOKEN')
        self._records_cache: Dict[str, AnalysisRecord] = {}
        
    @property
    def is_available(self) -> bool:
        return self.token is not None
    
    def upload_file(self, filename: str, data: bytes) -> str:
        """上传文件到 Vercel Blob"""
        if not self.is_available:
            raise RuntimeError("Vercel Blob token not configured")
        
        try:
            import requests
            
            response = requests.put(
                f"https://blob.vercel-storage.com/{filename}",
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": "application/octet-stream",
                    "x-api-version": "7",
                },
                data=data
            )
            response.raise_for_status()
            result = response.json()
            return result.get('url', '')
        except Exception as e:
            raise RuntimeError(f"Upload failed: {e}")
    
    def download_file(self, url: str) -> bytes:
        """从 Vercel Blob 下载文件"""
        import requests
        response = requests.get(url)
        response.raise_for_status()
        return response.content
    
    def delete_file(self, url: str) -> bool:
        """从 Vercel Blob 删除文件"""
        if not self.is_available:
            return False
        
        try:
            import requests
            response = requests.delete(
                url,
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "x-api-version": "7",
                }
            )
            return response.status_code == 200
        except:
            return False
    
    def save_record(self, record: AnalysisRecord) -> bool:
        """保存分析记录到 Vercel Blob"""
        try:
            # 保存记录为 JSON
            record_json = json.dumps(record.to_dict(), ensure_ascii=False)
            self.upload_file(f"records/{record.id}.json", record_json.encode('utf-8'))
            self._records_cache[record.id] = record
            return True
        except:
            return False
    
    def get_records(self) -> List[AnalysisRecord]:
        """获取所有分析记录"""
        # Vercel Blob 需要 list API，这里简化处理
        return list(self._records_cache.values())
    
    def get_record(self, record_id: str) -> Optional[AnalysisRecord]:
        """获取单个分析记录"""
        return self._records_cache.get(record_id)
    
    def delete_record(self, record_id: str) -> bool:
        """删除分析记录"""
        record = self._records_cache.pop(record_id, None)
        if record and record.file_url:
            self.delete_file(record.file_url)
        return record is not None


class LocalStorage(CloudStorage):
    """本地存储实现（开发/本地使用）"""
    
    def __init__(self, base_path: str = None):
        if base_path is None:
            base_path = os.path.join(tempfile.gettempdir(), 'odoo_depends_storage')
        self.base_path = Path(base_path)
        self.files_path = self.base_path / 'files'
        self.records_path = self.base_path / 'records'
        
        # 创建目录
        self.files_path.mkdir(parents=True, exist_ok=True)
        self.records_path.mkdir(parents=True, exist_ok=True)
    
    @property
    def is_available(self) -> bool:
        return True
    
    def upload_file(self, filename: str, data: bytes) -> str:
        """保存文件到本地"""
        # 生成唯一文件名，只取文件名部分（去除路径）
        base_filename = os.path.basename(filename)
        file_hash = hashlib.md5(data).hexdigest()[:8]
        safe_filename = f"{file_hash}_{base_filename}"
        file_path = self.files_path / safe_filename
        
        with open(file_path, 'wb') as f:
            f.write(data)
        
        return f"local://{file_path}"
    
    def download_file(self, url: str) -> bytes:
        """从本地读取文件"""
        if url.startswith('local://'):
            file_path = url[8:]  # 移除 'local://' 前缀
            with open(file_path, 'rb') as f:
                return f.read()
        raise ValueError(f"Invalid local URL: {url}")
    
    def delete_file(self, url: str) -> bool:
        """删除本地文件"""
        if url.startswith('local://'):
            file_path = Path(url[8:])
            if file_path.exists():
                file_path.unlink()
                return True
        return False
    
    def save_record(self, record: AnalysisRecord) -> bool:
        """保存分析记录到本地"""
        try:
            record_path = self.records_path / f"{record.id}.json"
            with open(record_path, 'w', encoding='utf-8') as f:
                json.dump(record.to_dict(), f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"保存记录失败: {e}")
            return False
    
    def get_records(self) -> List[AnalysisRecord]:
        """获取所有分析记录"""
        records = []
        for record_file in self.records_path.glob('*.json'):
            try:
                with open(record_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    records.append(AnalysisRecord(**data))
            except Exception as e:
                print(f"读取记录失败 {record_file}: {e}")
        
        # 按上传时间倒序排列
        records.sort(key=lambda r: r.upload_time, reverse=True)
        return records
    
    def get_record(self, record_id: str) -> Optional[AnalysisRecord]:
        """获取单个分析记录"""
        record_path = self.records_path / f"{record_id}.json"
        if record_path.exists():
            try:
                with open(record_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return AnalysisRecord(**data)
            except:
                pass
        return None
    
    def delete_record(self, record_id: str) -> bool:
        """删除分析记录"""
        record = self.get_record(record_id)
        if record:
            # 删除 ZIP 文件
            if record.file_url:
                self.delete_file(record.file_url)
            # 删除记录文件
            record_path = self.records_path / f"{record_id}.json"
            if record_path.exists():
                record_path.unlink()
            return True
        return False
    
    def get_storage_info(self) -> Dict[str, Any]:
        """获取存储信息"""
        total_size = 0
        file_count = 0
        
        for f in self.files_path.glob('*'):
            if f.is_file():
                total_size += f.stat().st_size
                file_count += 1
        
        record_count = len(list(self.records_path.glob('*.json')))
        
        return {
            'path': str(self.base_path),
            'total_size': total_size,
            'total_size_mb': round(total_size / 1024 / 1024, 2),
            'file_count': file_count,
            'record_count': record_count,
        }
    
    def clear_storage(self) -> bool:
        """清空存储"""
        try:
            shutil.rmtree(self.base_path)
            self.files_path.mkdir(parents=True, exist_ok=True)
            self.records_path.mkdir(parents=True, exist_ok=True)
            return True
        except:
            return False


def get_storage() -> CloudStorage:
    """获取存储实例（自动选择 Vercel Blob 或本地存储）"""
    vercel_storage = VercelBlobStorage()
    if vercel_storage.is_available:
        return vercel_storage
    return LocalStorage()


def generate_record_id() -> str:
    """生成唯一记录 ID"""
    import uuid
    return str(uuid.uuid4())[:8]
