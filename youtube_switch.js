/**
 * Surge 策略组自动切换脚本
 */

// === 用户配置区 ===
const GROUP_NAME = 'YouTube';     // 修改为匹配您截图中的策略组名称
const PEAK_NODE = '美国节点';      // 晚高峰切换到的节点
const OFF_PEAK_NODE = '日本节点';  // 闲时切换到的节点
// ===================

const currentHour = new Date().getHours();
// 晚高峰时间：大于等于 20 点（20:00-23:59）或 小于 2 点（00:00-01:59）
const isPeak = (currentHour >= 20 || currentHour < 2);

const targetNode = isPeak ? PEAK_NODE : OFF_PEAK_NODE;
const timeLabel = isPeak ? '晚高峰' : '闲时';

// 核心 API：执行 Surge 策略组切换
$surge.setSelectGroupPolicy(GROUP_NAME, targetNode);

// 记录日志并发送通知
console.log(`[YouTube 自动切换] 当前时间 ${currentHour}:00 (${timeLabel})，已切换至节点: ${targetNode}`);
$notification.post("YouTube 线路自动切换", `当前时段: ${timeLabel}`, `已成功切换至节点: ${targetNode}`);

$done();
