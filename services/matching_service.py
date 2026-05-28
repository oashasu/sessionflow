"""会话-需求匹配服务"""

from typing import Optional

from core.storage import get_storage, RequirementSessionLink
from core.errors import NotFoundError


class MatchingService:
    """会话-需求匹配服务"""

    def __init__(self):
        self.storage = get_storage()

    def link_session(
        self,
        req_id: str,
        session_id: str,
        role: str = 'secondary',
        notes: str = ''
    ) -> RequirementSessionLink:
        """关联会话到需求

        Args:
            req_id: 需求ID
            session_id: 会话ID
            role: 角色（primary/secondary/reference）
            notes: 关联说明

        Returns:
            关联链接对象

        Raises:
            NotFoundError: 需求不存在
        """
        req = self.storage.get_requirement(req_id)
        if not req:
            raise NotFoundError('需求', req_id)

        link = RequirementSessionLink.create(
            requirement_id=req_id,
            session_id=session_id,
            role=role,
            notes=notes
        )
        self.storage.link_session_to_requirement(link)
        return link

    def unlink_session(self, session_id: str) -> bool:
        """解除会话关联

        Args:
            session_id: 会话ID

        Returns:
            是否成功解除
        """
        return self.storage.unlink_session(session_id)

    def get_session_requirement(self, session_id: str) -> Optional[RequirementSessionLink]:
        """获取会话所属的需求关联

        Args:
            session_id: 会话ID

        Returns:
            关联链接对象（若无关联则返回None）
        """
        return self.storage.get_session_requirement(session_id)

    def get_requirement_sessions(self, req_id: str) -> list:
        """获取需求关联的所有会话

        Args:
            req_id: 需求ID

        Returns:
            关联链接列表

        Raises:
            NotFoundError: 需求不存在
        """
        req = self.storage.get_requirement(req_id)
        if not req:
            raise NotFoundError('需求', req_id)

        return self.storage.get_requirement_sessions(req_id)