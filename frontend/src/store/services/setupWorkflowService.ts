import * as api from '../../api/client';
import type { Participant } from '../../types/cad';

export interface SetupWorkflowCallbacks {
  onWelcome: (participants: Record<string, Participant>) => void;
  onParticipantJoined: (participant: Participant) => void;
  onParticipantLeft: (participantId: string) => void;
  onChatMessage: (message: {
    participant_id: string;
    participant_name: string;
    color: string;
    message: string;
    timestamp: string;
  }) => void;
}

export function createCollaborationWorkflow(
  sessionId: string,
  callbacks: SetupWorkflowCallbacks,
): api.CollaborationClient {
  const client = new api.CollaborationClient(sessionId);

  client.on('welcome', (event) => {
    const sessionState = event.session_state as { participants?: Record<string, unknown> } | undefined;
    const participants = (sessionState?.participants ?? {}) as Record<string, Participant>;
    callbacks.onWelcome(participants);
  });

  client.on('participant_joined', (event) => {
    callbacks.onParticipantJoined(event.participant as Participant);
  });

  client.on('participant_left', (event) => {
    callbacks.onParticipantLeft(event.participant_id as string);
  });

  client.on('chat_message', (event) => {
    callbacks.onChatMessage({
      participant_id: event.participant_id as string,
      participant_name: event.participant_name as string,
      color: event.color as string,
      message: event.message as string,
      timestamp: event.timestamp as string,
    });
  });

  return client;
}
