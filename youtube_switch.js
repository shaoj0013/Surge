/**
 * Surge 策略组自动切换脚本 (多组批量版)
 */

// === 用户配置区 ===
// 将所有需要参与闲忙时切换的策略组名称放进这个数组里
const GROUP_NAMES = [
  'Netflix',
  'Disney Plus',
  'Max',
  'Twitter',
  'YouTube',
  'Telegram',
  'Microsoft',
  'TikTok'
];

const PEAK_NODE = '美国节点';      // 晚高峰切换到的节点
const OFF_PEAK_NODE = '日本节点';  // 闲时切换到的节点
// ===================

const currentHour = new Date().getHours();
// 晚高峰时间：大于等于 20 点（20:00-23:59）或 小于 2 点（00:00-01:59）
const isPeak = (currentHour >= 20 || currentHour < 2);

const targetNode = isPeak ? PEAK_NODE : OFF_PEAK_NODE;
const timeLabel = isPeak ? '晚高峰' : '闲时';

// 核心 API：遍历数组，批量执行 Surge 策略组切换
GROUP_NAMES.forEach(group => {
  $surge.setSelectGroupPolicy(group, targetNode);
});

// 记录日志并发送一条汇总通知
console.log(`[线路自动切换] 当前时间 ${currentHour}:00 (${timeLabel})，已将 ${GROUP_NAMES.length} 个策略组切换至节点: ${targetNode}`);
$notification.post("线路自动切换完毕", `当前时段: ${timeLabel}`, `已成功将 Proxy, Netflix 等 ${GROUP_NAMES.length} 个组切换至: ${targetNode}`);

$done();
