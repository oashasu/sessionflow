// utils.js - 工具函数

function escapeHtml(text) {
    if (!text) return '';
    return String(text).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function formatDate(timestamp) {
    if (!timestamp) return '';
    return new Date(timestamp).toLocaleString('zh-CN');
}

function formatDuration(startMs, endMs) {
    if (!startMs || !endMs) return '';
    const minutes = ((endMs - startMs) / 1000 / 60).toFixed(1);
    return `${minutes} 分钟`;
}

function truncateText(text, maxLength = 50) {
    if (!text) return '';
    return text.length > maxLength ? text.substring(0, maxLength) + '...' : text;
}

function debounce(fn, delay = 300) {
    let timer = null;
    return function (...args) {
        clearTimeout(timer);
        timer = setTimeout(() => fn.apply(this, args), delay);
    };
}
