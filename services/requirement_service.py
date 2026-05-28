"""需求管理服务"""

from typing import List, Optional
from datetime import datetime

from core.storage import get_storage, Requirement, RequirementSessionLink
from core.errors import NotFoundError, ConflictError, ValidationError


class RequirementService:
    """需求管理服务"""

    def __init__(self):
        self.storage = get_storage()

    def list(self, category: str = 'all') -> List[Requirement]:
        """获取需求列表

        Args:
            category: 分类筛选（all/feature/bug/refactor/docs/other）

        Returns:
            需求列表，按创建时间倒序排列
        """
        reqs = self.storage.load_requirements()
        if category != 'all':
            reqs = [r for r in reqs if r.category == category]
        return sorted(reqs, key=lambda r: r.created_at, reverse=True)

    def create(
        self,
        title: str,
        category: str = 'feature',
        priority: str = 'p2',
        work_dirs: List[str] = [],
        description: str = '',
        tags: List[str] = [],
        session_ids: List[str] = []
    ) -> Requirement:
        """创建需求

        Args:
            title: 需求标题（必填）
            category: 分类（feature/bug/refactor/docs/other）
            priority: 优先级（p0/p1/p2/p3）
            work_dirs: 关联工作目录
            description: 详细描述
            tags: 标签列表
            session_ids: 自动关联的会话ID列表

        Returns:
            新创建的需求

        Raises:
            ValidationError: 标题为空
            ConflictError: 已存在相同标题的需求
        """
        if not title or not title.strip():
            raise ValidationError('title', '标题不能为空')

        title = title.strip()

        # 检查是否已存在（标题唯一）
        existing = self.storage.load_requirements()
        for req in existing:
            if req.title == title and req.status != 'archived':
                raise ConflictError('需求', 'title', title)

        req = Requirement.create(
            title=title,
            category=category,
            priority=priority,
            work_dirs=work_dirs,
            description=description,
            tags=tags
        )
        self.storage.add_requirement(req)

        # 自动关联session
        for sid in session_ids:
            link = RequirementSessionLink.create(sid, req.id, role='primary')
            self.storage.link_session_to_requirement(link)

        return req

    def get_detail(self, req_id: str) -> Optional[dict]:
        """获取需求详情（含关联sessions）

        Args:
            req_id: 需求ID

        Returns:
            需求详情字典，包含linked_sessions字段

        Raises:
            NotFoundError: 需求不存在
        """
        req = self.storage.get_requirement(req_id)
        if not req:
            raise NotFoundError('需求', req_id)

        # 获取关联session（批量查询避免N+1）
        links = self.storage.get_requirement_sessions(req_id)
        session_ids = [link.session_id for link in links]
        sessions_map = self.storage.get_sessions_by_ids(session_ids)

        linked_sessions = []
        for link in links:
            session = sessions_map.get(link.session_id)
            if session:
                linked_sessions.append({
                    'session_id': link.session_id,
                    'short_id': session.get('session_id', link.session_id)[:8],
                    'project_name': session.get('project_name', ''),
                    'topic': session.get('topic', ''),
                    'role': link.role,
                    'notes': link.notes,
                    'linked_at': link.linked_at,
                })
            else:
                linked_sessions.append({
                    'session_id': link.session_id,
                    'short_id': link.session_id[:8],
                    'project_name': '(会话已过期)',
                    'topic': '',
                    'role': link.role,
                    'notes': link.notes,
                    'linked_at': link.linked_at,
                })

        return {
            'id': req.id,
            'title': req.title,
            'description': req.description,
            'category': req.category,
            'status': req.status,
            'priority': req.priority,
            'tags': req.tags,
            'work_dirs': req.work_dirs,
            'created_at': req.created_at,
            'updated_at': req.updated_at,
            'completed_at': req.completed_at,
            'linked_sessions': linked_sessions,
        }

    def update(self, req_id: str, **kwargs) -> bool:
        """更新需求

        Args:
            req_id: 需求ID
            **kwargs: 要更新的字段

        Returns:
            是否更新成功

        Raises:
            NotFoundError: 需求不存在
        """
        req = self.storage.get_requirement(req_id)
        if not req:
            raise NotFoundError('需求', req_id)

        return self.storage.update_requirement(req_id, **kwargs)

    def complete(self, req_id: str) -> bool:
        """完成需求

        Args:
            req_id: 需求ID

        Returns:
            是否成功

        Raises:
            NotFoundError: 需求不存在
        """
        now = int(datetime.now().timestamp() * 1000)
        return self.update(req_id, status='completed', completed_at=now)

    def delete(self, req_id: str) -> bool:
        """删除需求（同时删除关联links）

        Args:
            req_id: 需求ID

        Returns:
            是否删除成功

        Raises:
            NotFoundError: 需求不存在
        """
        req = self.storage.get_requirement(req_id)
        if not req:
            raise NotFoundError('需求', req_id)

        # remove_requirement会自动删除关联links
        return self.storage.remove_requirement(req_id)