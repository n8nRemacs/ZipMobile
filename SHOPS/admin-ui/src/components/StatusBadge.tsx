import { Tag } from 'antd'

const STATUS_COLORS: Record<string, string> = {
  pending: 'orange',
  resolved: 'green',
  normalized: 'green',
  needs_moderation: 'volcano',
  not_spare_part: 'default',
  running: 'blue',
  completed: 'green',
  failed: 'red',
}

interface Props {
  status: string
}

export default function StatusBadge({ status }: Props) {
  return <Tag color={STATUS_COLORS[status] || 'default'}>{status}</Tag>
}
