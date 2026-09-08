import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import User
from .models import Notification


class NotificationConsumer(AsyncWebsocketConsumer):
    """Consumer para notificaciones en tiempo real"""
    
    async def connect(self):
        self.user = self.scope["user"]
        
        if self.user.is_anonymous:
            await self.close()
            return
        
        self.group_name = f"user_{self.user.id}"
        
        # Unirse al grupo del usuario
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Enviar contador de no leídos al conectar
        unread_count = await self.get_unread_count()
        await self.send(text_data=json.dumps({
            'type': 'unread_count',
            'count': unread_count
        }))
    
    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )
    
    async def receive(self, text_data):
        data = json.loads(text_data)
        message_type = data.get('type')
        
        if message_type == 'mark_read':
            notification_id = data.get('notification_id')
            await self.mark_as_read(notification_id)
        elif message_type == 'mark_all_read':
            await self.mark_all_as_read()
        elif message_type == 'get_notifications':
            notifications = await self.get_notifications()
            await self.send(text_data=json.dumps({
                'type': 'notifications_list',
                'notifications': notifications
            }))
    
    async def notification_message(self, event):
        """Enviar notificación al WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'notification_message',
            'notification': event['notification']
        }))
    
    async def unread_count_update(self, event):
        """Actualizar contador de no leídos"""
        await self.send(text_data=json.dumps({
            'type': 'unread_count',
            'count': event['count']
        }))
    
    @database_sync_to_async
    def get_unread_count(self):
        return Notification.objects.filter(
            recipient=self.user, 
            is_read=False
        ).count()
    
    @database_sync_to_async
    def mark_as_read(self, notification_id):
        try:
            notification = Notification.objects.get(
                id=notification_id, 
                recipient=self.user
            )
            notification.is_read = True
            notification.save()
            
            # Enviar contador actualizado
            unread_count = Notification.objects.filter(
                recipient=self.user, 
                is_read=False
            ).count()
            
            return unread_count
        except Notification.DoesNotExist:
            return None
    
    @database_sync_to_async
    def mark_all_as_read(self):
        Notification.objects.filter(
            recipient=self.user, 
            is_read=False
        ).update(is_read=True)
        
        return 0
    
    @database_sync_to_async
    def get_notifications(self, limit=50):
        notifications = Notification.objects.filter(
            recipient=self.user
        ).select_related('sender')[:limit]
        
        return [
            {
                'id': n.id,
                'type': n.notification_type,
                'title': n.title,
                'message': n.message,
                'sender': n.sender.username if n.sender else None,
                'sender_avatar': n.sender.profile.logo.url if n.sender and hasattr(n.sender, 'profile') and n.sender.profile.logo else None,
                'is_read': n.is_read,
                'created_at': n.created_at.isoformat(),
                'related_object_id': n.related_object_id,
                'related_object_type': n.related_object_type,
                'icon': n.icon,
            }
            for n in notifications
        ]


class ChatConsumer(AsyncWebsocketConsumer):
    """Consumer para mensajería en tiempo real"""
    
    async def connect(self):
        self.user = self.scope["user"]
        self.conversation_id = self.scope['url_route']['kwargs']['conversation_id']
        
        if self.user.is_anonymous:
            await self.close()
            return
        
        # Verificar que el usuario pertenece a la conversación
        can_access = await self.can_access_conversation()
        if not can_access:
            await self.close()
            return
        
        self.group_name = f"conversation_{self.conversation_id}"
        
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        
        await self.accept()
    
    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )
    
    async def receive(self, text_data):
        data = json.loads(text_data)
        message_type = data.get('type')
        
        if message_type == 'chat_message':
            content = data.get('content')
            await self.save_message(content)
        elif message_type == 'typing':
            await self.channel_layer.group_send(
                self.group_name,
                {
                    'type': 'user_typing',
                    'user_id': self.user.id,
                    'username': self.user.username,
                }
            )
        elif message_type == 'read_receipt':
            message_id = data.get('message_id')
            await self.mark_as_read(message_id)
    
    async def chat_message(self, event):
        """Enviar mensaje al WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'chat_message',
            'message': event['message']
        }))
    
    async def user_typing(self, event):
        """Notificar que usuario está escribiendo"""
        if event['user_id'] != self.user.id:
            await self.send(text_data=json.dumps({
                'type': 'typing',
                'user_id': event['user_id'],
                'username': event['username'],
            }))
    
    async def read_receipt(self, event):
        """Confirmación de lectura"""
        await self.send(text_data=json.dumps({
            'type': 'read_receipt',
            'message_id': event['message_id'],
            'user_id': event['user_id'],
        }))
    
    @database_sync_to_async
    def can_access_conversation(self):
        from messaging.models import Conversation
        from users.models import Profile
        try:
            conversation = Conversation.objects.get(id=self.conversation_id)
            # Verificar si el usuario actual es user1 o user2 en la conversación
            profile = Profile.objects.get(user=self.user)
            return conversation.user1 == profile or conversation.user2 == profile
        except (Conversation.DoesNotExist, Profile.DoesNotExist):
            return False
    
    @database_sync_to_async
    def save_message(self, content):
        from messaging.models import Conversation, Message
        from users.models import Profile
        conversation = Conversation.objects.get(id=self.conversation_id)
        sender_profile = Profile.objects.get(user=self.user)
        
        # Determinar destinatario
        recipient_profile = conversation.user2 if conversation.user1 == sender_profile else conversation.user1
        
        message = Message.objects.create(
            sender=sender_profile,
            recipient=recipient_profile,
            content=content
        )
        conversation.updated_at = message.timestamp
        conversation.save()
        
        return {
            'id': message.id,
            'content': message.content,
            'sender_id': self.user.id,
            'sender_username': self.user.username,
            'sender_avatar': sender_profile.logo.url if sender_profile.logo else None,
            'created_at': message.timestamp.isoformat(),
            'read_by': [],
        }
    
    @database_sync_to_async
    def mark_as_read(self, message_id):
        from messaging.models import Message
        from users.models import Profile
        try:
            profile = Profile.objects.get(user=self.user)
            message = Message.objects.get(id=message_id, recipient=profile)
            message.read_by.add(profile)
            return True
        except (Message.DoesNotExist, Profile.DoesNotExist):
            return False