import type { AiMessageData } from '../../lib/types'

interface Props {
  message: AiMessageData
}

export function AiMessage({ message }: Props) {
  return (
    <div className={`ai-message ${message.role}`}>
      <div className="ai-message-text">{message.text}</div>
    </div>
  )
}
