<script setup lang="ts">
import { NCheckbox, NSpace } from 'naive-ui'

const model = defineModel<string[]>({ required: true })

const channels = [
  { value: 'telegram', label: 'Telegram (вы здесь)', disabled: true },
  { value: 'whatsapp', label: 'WhatsApp' },
  { value: 'vk_max', label: 'VK Max' },
]

function toggle(channel: string, checked: boolean) {
  if (channel === 'telegram') return // always checked
  if (checked) {
    model.value = [...model.value, channel]
  } else {
    model.value = model.value.filter(c => c !== channel)
  }
}
</script>

<template>
  <NSpace vertical :size="8">
    <NCheckbox
      v-for="ch in channels"
      :key="ch.value"
      :checked="model.includes(ch.value)"
      :disabled="ch.disabled"
      @update:checked="(val: boolean) => toggle(ch.value, val)"
    >
      {{ ch.label }}
    </NCheckbox>
  </NSpace>
</template>
