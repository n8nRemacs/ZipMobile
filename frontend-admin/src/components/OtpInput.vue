<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'

const props = defineProps<{
  length?: number
  disabled?: boolean
}>()

const emit = defineEmits<{
  complete: [code: string]
}>()

const digits = props.length || 6
const inputs = ref<HTMLInputElement[]>([])
const values = ref<string[]>(Array(digits).fill(''))

function setRef(el: any, i: number) {
  if (el) inputs.value[i] = el
}

function onInput(e: Event, i: number) {
  const input = e.target as HTMLInputElement
  const val = input.value.replace(/\D/g, '')
  values.value[i] = val.slice(0, 1)
  input.value = values.value[i]

  if (val && i < digits - 1) {
    inputs.value[i + 1]?.focus()
  }

  const code = values.value.join('')
  if (code.length === digits) {
    emit('complete', code)
  }
}

function onKeydown(e: KeyboardEvent, i: number) {
  if (e.key === 'Backspace' && !values.value[i] && i > 0) {
    values.value[i - 1] = ''
    inputs.value[i - 1]?.focus()
  }
}

function onPaste(e: ClipboardEvent) {
  e.preventDefault()
  const text = (e.clipboardData?.getData('text') || '').replace(/\D/g, '').slice(0, digits)
  for (let i = 0; i < digits; i++) {
    values.value[i] = text[i] || ''
  }
  // Focus last filled or next empty
  const nextIdx = Math.min(text.length, digits - 1)
  nextTick(() => inputs.value[nextIdx]?.focus())

  if (text.length === digits) {
    emit('complete', text)
  }
}

onMounted(() => {
  nextTick(() => inputs.value[0]?.focus())
})
</script>

<template>
  <div class="otp-container" @paste="onPaste">
    <input
      v-for="(_, i) in digits"
      :key="i"
      :ref="(el) => setRef(el, i)"
      type="text"
      inputmode="numeric"
      maxlength="1"
      class="otp-digit"
      :class="{ filled: values[i] }"
      :value="values[i]"
      :disabled="disabled"
      @input="(e) => onInput(e, i)"
      @keydown="(e) => onKeydown(e, i)"
    />
  </div>
</template>

<style scoped>
.otp-container {
  display: flex;
  gap: 8px;
  justify-content: center;
}
.otp-digit {
  width: 44px;
  height: 52px;
  text-align: center;
  font-size: 22px;
  font-weight: 600;
  border: 1.5px solid #d9d9d9;
  border-radius: 8px;
  outline: none;
  transition: border-color 0.2s;
  font-family: inherit;
}
.otp-digit:focus {
  border-color: #3B82F6;
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.15);
}
.otp-digit.filled {
  border-color: #3B82F6;
}
.otp-digit:disabled {
  background: #f5f5f5;
  color: #999;
}
</style>
