// VPS 流量面板脚本
// 支持两种数据源：
//   1) widget 格式（推荐，数值已与服务商面板口径对齐）：
//      {"ok":true,"updatedAt":"...","products":[{"id":"...","nextinvoicedate":"2027-02-11",
//        "traffic":{"usedGb":23.43,"totalGb":1000,"remainGb":976.57,"resetDaysLeft":29,"unit":"GB"}}]}
//   2) 旧版 /data 格式（浏览器端抓取）：
//      {"expire":"2027-02-11","interfaces":[{"traffic":{"month":[{"rx":1,"tx":2}]}}]}

let args = {};
if (typeof $argument === 'string') {
    let pairs = $argument.split(',');
    for (let pair of pairs) {
        let idx = pair.indexOf('=');
        if (idx !== -1) {
            let key = pair.substring(0, idx).trim();
            let val = pair.substring(idx + 1).trim();
            args[key] = val;
        }
    }
}

let url = args.url;
let panelTitle = args.title || "VPS 流量监控";
let limitGB = parseFloat(args.limit || 1000);
let billingMode = args.billing || "sum";
let offsetGB = parseFloat(args.offset || 0);
let unitBase = parseInt(args.unit || args.base || 1024);
let expireDateArgs = args.expire;
let bytesPerGB = Math.pow(unitBase, 3);

// 按 resetDaysLeft / 到期日推算距离下次流量重置的天数
function resetDaysLeftFromDate(dateStr) {
    let targetDate = new Date(dateStr + "T00:00:00");
    if (isNaN(targetDate.getTime())) return null;

    let resetDay = targetDate.getDate();
    let now = new Date();
    let todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    let nextResetDate = new Date(now.getFullYear(), now.getMonth(), resetDay);
    if (now.getDate() >= resetDay) {
        nextResetDate = new Date(now.getFullYear(), now.getMonth() + 1, resetDay);
    }
    let diffTime = nextResetDate.getTime() - todayStart.getTime();
    return Math.ceil(diffTime / (1000 * 60 * 60 * 24));
}

function pickProduct(json) {
    let products = json?.products;
    if (!Array.isArray(products) || products.length === 0) return null;
    if (args.id) {
        let hit = products.find(p => p.id === args.id || p.accountKey === args.id);
        if (hit) return hit;
    }
    return products[0];
}

function latestBytes(arr) {
    if (!arr || !Array.isArray(arr) || arr.length === 0) return 0;
    let latest = arr[arr.length - 1];
    let rx = Number(latest.rx || 0);
    let tx = Number(latest.tx || 0);
    return billingMode === "max" ? Math.max(rx, tx) : rx + tx;
}

$httpClient.get({url: url}, function(error, response, data) {
    if (error) {
        $done({title: panelTitle, content: "网络错误: 无法连接 API", icon: "network.slash"});
        return;
    }

    try {
        let json = JSON.parse(data);
        let usedGB, totalGB, remainGB, unit, dateString, resetDaysLeft, updatedAt;
        let originLabel = "";

        let product = pickProduct(json);
        if (product) {
            // ---- widget 格式：数值由服务端按面板口径计算 ----
            let traffic = product.traffic || {};
            usedGB = Number(traffic.usedGb || 0);
            totalGB = Number(traffic.totalGb || limitGB || 0);
            remainGB = traffic.remainGb !== undefined
                ? Number(traffic.remainGb)
                : Math.max(0, totalGB - usedGB);
            unit = traffic.unit || "GB";
            dateString = product.nextinvoicedate || product.renewal?.nextDueDate || expireDateArgs || "未设置";
            resetDaysLeft = traffic.resetDaysLeft !== undefined
                ? Number(traffic.resetDaysLeft)
                : (product.renewal?.resetDaysLeft !== undefined
                    ? Number(product.renewal.resetDaysLeft)
                    : resetDaysLeftFromDate(dateString));
            updatedAt = json.updatedAtLocal || json.updatedAt || "";
            // 数据来源标注: 面板推送 / 实时自采集 / 面板数据已过期
            let traffic = product.traffic || {};
            if (traffic.dataOrigin === "panel-push") {
                originLabel = traffic.panelCapturedAt
                    ? `面板采集于 ${traffic.panelCapturedAt}`
                    : "面板推送";
            } else if (traffic.panelStale) {
                originLabel = `实时自采集(面板数据已过期 ${Math.round((traffic.panelAgeMin || 0) / 60)}h)`;
            } else {
                originLabel = "实时自采集";
            }
        } else {
            // ---- 旧版 /data 格式 ----
            let traffic = json?.interfaces?.[0]?.traffic;
            if (!traffic) throw new Error("尚未接收到浏览器端数据");

            let monthBytes = latestBytes(traffic.month);
            usedGB = (monthBytes / bytesPerGB) + offsetGB;
            totalGB = limitGB;
            remainGB = Math.max(0, totalGB - usedGB);
            unit = unitBase === 1000 ? "GB" : "GiB";
            dateString = json?.expire || expireDateArgs || "未设置";
            resetDaysLeft = resetDaysLeftFromDate(dateString);
            updatedAt = "";
        }

        let usagePercent = totalGB > 0 ? ((usedGB / totalGB) * 100).toFixed(1) : "0.0";
        let usedText = Math.max(0, usedGB).toFixed(2);
        let remainText = Math.max(0, remainGB).toFixed(2);
        let totalText = totalGB > 0 ? totalGB.toFixed(0) : "--";
        let countdown = (resetDaysLeft === null || resetDaysLeft === undefined || isNaN(resetDaysLeft))
            ? "--"
            : resetDaysLeft + " 天";

        let content = `已用: ${usedText} ${unit} (${usagePercent}%)\n剩余: ${remainText} ${unit} / ${totalText} ${unit}`;
        content += `\n到期: ${dateString} (流量重置剩 ${countdown})`;
        if (originLabel) {
            content += `\n来源: ${originLabel}`;
        }
        if (updatedAt) {
            content += `\n更新: ${updatedAt}`;
        }

        $done({
            title: panelTitle,
            content: content,
            icon: "server.rack"
        });
    } catch (e) {
        $done({title: panelTitle, content: `异常: ${e.message}`, icon: "exclamationmark.triangle"});
    }
});
