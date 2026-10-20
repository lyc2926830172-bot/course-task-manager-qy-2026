// 删除操作通过 POST 提交，先提示用户确认；核心功能不依赖 JavaScript。
document.querySelectorAll('form[data-confirm]').forEach(function (form) {
  form.addEventListener('submit', function (event) {
    if (!window.confirm(form.dataset.confirm)) event.preventDefault();
  });
});

// 书写时给输入区域一个轻微反馈；不影响未启用 JavaScript 的表单提交。
document.querySelectorAll('input, select, textarea').forEach(function (field) {
  field.addEventListener('focus', function () { field.closest('.field, .filters > div')?.classList.add('is-writing'); });
  field.addEventListener('blur', function () { field.closest('.field, .filters > div')?.classList.remove('is-writing'); });
});
