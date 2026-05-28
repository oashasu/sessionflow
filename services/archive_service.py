"""归档管理服务"""

from typing import List, Optional

from core.storage import get_storage, ArchivedSession
from core.errors import NotFoundError, ValidationError


class ArchiveService:
    """归档管理服务"""

    def __init__(self):
        self.storage = get_storage()

    def archive(
        self,
        session_id: str,
        archive_type: str = 'archived',
        insight: str = '',
        reason: str = '',
        project_name: str = '',
        topic: str = ''
    ) -> ArchivedSession:
        """归档会话

        Args:
            session_id: 会话ID
            archive_type: 归档类型（archived/trash）
            insight: 归档反思
            reason: 归档原因
            project_name: 项目名（便于查询）
            topic: 主题

        Returns:
            归档记录对象
        """
        archived = ArchivedSession.create(
            session_id=session_id,
            archive_type=archive_type,
            insight=insight,
            reason=reason,
            project_name=project_name,
            topic=topic
        )

        # 检查是否已存在归档记录
        existing = self.storage.get_archived_session(session_id)
        if existing:
            # 更新现有记录
            self.storage.archive_session(
                session_id,
                archive_type=archive_type,
                insight=insight,
                reason=reason,
                project_name=project_name,
                topic=topic
            )
            return self.storage.get_archived_session(session_id)

        self.storage.archive_session(
            session_id,
            archive_type=archive_type,
            insight=insight,
            reason=reason,
            project_name=project_name,
            topic=topic
        )
        return archived

    def trash(self, session_id: str, reason: str = '') -> ArchivedSession:
        """移动会话到废纸篓

        Args:
            session_id: 会话ID
            reason: 删除原因

        Returns:
            归档记录对象
        """
        return self.archive(session_id, archive_type='trash', reason=reason)

    def restore(self, session_id: str) -> bool:
        """恢复会话（从归档中移除）

        Args:
            session_id: 会话ID

        Returns:
            是否成功恢复

        Raises:
            NotFoundError: 会话不在归档中
        """
        archived = self.storage.get_archived_session(session_id)
        if not archived:
            raise NotFoundError('归档会话', session_id)

        return self.storage.restore_session(session_id)

    def delete_permanently(self, session_id: str) -> bool:
        """永久删除（仅限废纸篓中的会话）

        Args:
            session_id: 会话ID

        Returns:
            是否成功删除

        Raises:
            NotFoundError: 会话不在废纸篓中
            ValidationError: 会话不是trash类型
        """
        archived = self.storage.get_archived_session(session_id)
        if not archived:
            raise NotFoundError('归档会话', session_id)

        if archived.archive_type != 'trash':
            raise ValidationError('archive_type', '仅能永久删除废纸篓中的会话')

        return self.storage.delete_trash_session(session_id)

    def list_archived(self, archive_type: Optional[str] = None) -> List[ArchivedSession]:
        """获取归档会话列表

        Args:
            archive_type: 类型筛选（None表示全部）

        Returns:
            归档会话列表
        """
        if archive_type:
            return self.storage.get_archived_by_type(archive_type)
        return self.storage.load_archived_sessions()

    def get_archived(self, session_id: str) -> Optional[ArchivedSession]:
        """获取归档记录

        Args:
            session_id: 会话ID

        Returns:
            归档记录对象
        """
        return self.storage.get_archived_session(session_id)