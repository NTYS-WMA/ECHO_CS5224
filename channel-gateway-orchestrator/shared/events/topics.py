"""
Topic constants for the internal async messaging layer.

These mirror the domain event channels described in the architecture doc.
"""

#Conversation Flow
CONVERSATION_MESSAGE_RECEIVED = "conversation.message.received"
CONVERSATION_OUTBOUND = "conversation.outbound"
CONVERSATION_PROCESSING_FAILED = "conversation.processing.failed"

#User Profile
USER_PROFILE_UPDATED = "user.profile.updated"

#Relationship
RELATIONSHIP_INTERACTION_RECORDED = "relationship.interaction.recorded"
RELATIONSHIP_SCORE_UPDATED = "relationship.score.updated"
RELATIONSHIP_DECAY_REQUESTED = "relationship.decay.requested"

#Memory
MEMORY_SUMMARY_REQUESTED = "memory.summary.requested"
MEMORY_SUMMARY_COMPLETED = "memory.summary.completed"
MEMORY_COMPACTION_REQUESTED = "memory.compaction.requested"

#AI Generation
AI_GENERATION_FAILED = "ai.generation.failed"
AI_GENERATION_COMPLETED = "ai.generation.completed"

#Media
MEDIA_ASSET_READY = "media.asset.ready"
MEDIA_GENERATION_FAILED = "media.generation.failed"

#Cron
CRON_SCAN_REQUESTED = "cron.scan.requested"
CRON_DISPATCH_COMPLETED = "cron.dispatch.completed"
