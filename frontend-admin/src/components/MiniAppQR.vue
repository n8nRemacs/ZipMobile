<script setup lang="ts">
import QrcodeVue from 'qrcode.vue'

const botUrl = 'https://t.me/zipmobile_bot'
</script>

<template>
  <div class="qr-section">
    <QrcodeVue :value="botUrl" :size="160" level="M" />
    <div class="qr-info">
      <a :href="botUrl" target="_blank" class="bot-link">@zipmobile_bot</a>
      <span class="bot-url">t.me/zipmobile_bot</span>
    </div>
  </div>
</template>

<style scoped>
.qr-section {
  display: flex;
  align-items: center;
  gap: 20px;
}
.qr-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.bot-link {
  font-size: 16px;
  font-weight: 600;
  color: #0088cc;
  text-decoration: none;
}
.bot-link:hover {
  text-decoration: underline;
}
.bot-url {
  font-size: 13px;
  color: #999;
}
</style>
