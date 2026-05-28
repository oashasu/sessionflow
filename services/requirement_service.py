"""需求管理Service"""
from typing import List, Optional

from core import get_storage, Requirement, RequirementSessionLink


class RequirementService:
    """需求管理业务逻辑"""

    def __init__(self):
        self.storage = get_storage()

    def list(self, category: str = 'all') -> List[Requirement]:
        """获取需求列表（支持分类筛选）"""
        reqs = self.storage.load_requirements()
        if category != 'all':
            reqs = [r for r in reqs if r.category == category]
        return sorted(reqs, key=lambda r: r.created_at, reverse=True)

    def create(self, title: str, category: str = 'feature',
               priority: str = 'p2', description: str = '',
               tags: List[str] = None, work_dirs: List[str] = None,
               session_ids: List[str] = None) -> Requirement:
        """创建需求（幂等：检查是否已存在相同title）"""
        existing = self.storage.load_requirements()

        # 标题去重检查
        for req in existing:
            if req.title == title and req.status != 'archived':
                raise ValueError(f'需求"{title}"已存在，不允许重复创建')

        req = Requirement.create(
            title=title,
            category=category,
            priority=priority,
            description=description,
            tags=tags or [],
            work_dirs=work_dirs or [],
        )
        self.storage.add_requirement(req)

        # 自动关联session
        if session_ids:
            for sid in session_ids:
                link = RequirementSessionLink.create(sid, req.id, role='primary')
                self.storage.link_session_to_requirement(link)

        return req

    def get_detail(self, req_id: str) -> Optional[Requirement]:
        """获取需求详情（含关联sessions）"""
        req = self.storage.get_requirement(req_id)
        if req:
            links = self.storage.get_requirement_sessions(req_id)
            req.linked_sessions = links  # 动态添加属性
        return req

    def update(self, req_id: str, **kwargs) -> bool:
        """更新需求"""
        return self.storage.update_requirement(req_id, **kwargs)

    def complete(self, req_id: str) -> bool:
        """完成需求"""
        from datetime import datetime
        now = int(datetime.now().timestamp() * 1000)
        return self.storage.update_requirement(req_id, status='completed', completed_at=now)

    def delete(self, req_id: str) -> bool:
        """删除需求（同时删除关联links）"""
        return self.storage.remove_requirement(req_id)

    def get_linked_sessions(self, req_id: str) -> List[RequirementSessionLink]:
        """获取需求关联的session列表"""
        return self.storage.get_requirement_sessions(req_id)

    def link_session(self, req_id: str, session_id: str,
                     role: str = 'secondary', notes: str = '') -> RequirementSessionLink:
        """关联session到需求"""
        link = RequirementSessionLink.create(req_id, session_id, role=role, notes=notes)
        self.storage.link_session_to_requirement(link)
        return link

    def unlink_session(self, session_id: str) -> bool:
        """解除session关联"""
        return self.storage.unlink_session(session_id)
