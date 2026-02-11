<script setup lang="ts">
import { ref, watch, computed } from 'vue'

const props = defineProps<{
  modelValue: string
  disabled?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const display = ref(formatPhone(props.modelValue))

function formatPhone(raw: string): string {
  // raw = "+7XXXXXXXXXX" or digits only
  const digits = raw.replace(/\D/g, '').replace(/^8/, '7')
  // skip country code '7'
  const d = digits.startsWith('7') ? digits.slice(1) : digits
  if (!d) return ''
  let result = '+7 ('
  result += d.slice(0, 3)
  if (d.length >= 3) result += ') '
  else { return result }
  result += d.slice(3, 6)
  if (d.length >= 6) result += '-'
  else { return result }
  result += d.slice(6, 8)
  if (d.length >= 8) result += '-'
  else { return result }
  result += d.slice(8, 10)
  return result
}

function toRaw(formatted: string): string {
  const digits = formatted.replace(/\D/g, '')
  if (digits.startsWith('7') || digits.startsWith('8')) {
    return '+7' + digits.slice(1)
  }
  return '+7' + digits
}

function onInput(e: Event) {
  const input = e.target as HTMLInputElement
  let digits = input.value.replace(/\D/g, '')
  // limit to 11 digits (7 + 10)
  if (digits.startsWith('7') || digits.startsWith('8')) {
    digits = '7' + digits.slice(1, 11)
  } else {
    digits = digits.slice(0, 10)
  }
  const fullDigits = digits.startsWith('7') ? digits : '7' + digits
  display.value = formatPhone('+' + fullDigits)
  emit('update:modelValue', toRaw(display.value))

  // Restore cursor position
  const el = input
  setTimeout(() => {
    el.value = display.value
  }, 0)
}

function onFocus() {
  if (!display.value) {
    display.value = '+7 ('
  }
}

const isValid = computed(() => {
  const digits = props.modelValue.replace(/\D/g, '')
  return digits.length === 11
})

watch(() => props.modelValue, (val) => {
  display.value = formatPhone(val)
})

defineExpose({ isValid })
</script>

<template>
  <input
    type="tel"
    class="phone-input"
    :value="display"
    :disabled="disabled"
    placeholder="+7 (___) ___-__-__"
    @input="onInput"
    @focus="onFocus"
    maxlength="18"
  />
</template>

<style scoped>
.phone-input {
  width: 100%;
  padding: 10px 12px;
  font-size: 16px;
  border: 1px solid #d9d9d9;
  border-radius: 6px;
  outline: none;
  transition: border-color 0.2s;
  font-family: inherit;
  letter-spacing: 0.5px;
}
.phone-input:focus {
  border-color: #3B82F6;
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.15);
}
.phone-input:disabled {
  background: #f5f5f5;
  color: #999;
}
</style>
