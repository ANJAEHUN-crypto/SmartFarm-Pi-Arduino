(function () {
  const serialStatus = document.getElementById('serialStatus');
  const btnSerialToggle = document.getElementById('btnSerialToggle');
  const modal = document.getElementById('modal');
  const modalCh = document.getElementById('modalCh');
  const onTime = document.getElementById('onTime');
  const offTime = document.getElementById('offTime');
  const days = document.getElementById('days');
  const modalSave = document.getElementById('modalSave');
  const modalCancel = document.getElementById('modalCancel');

  let scheduleEdit = { channel: null, index: null };

  function setSerialStatus(open) {
    serialStatus.textContent = open ? '연결됨' : '연결 안 됨';
    serialStatus.classList.toggle('connected', open);
    btnSerialToggle.textContent = open ? '끊기' : '연결';
  }

  async function fetchSerialStatus() {
    try {
      const r = await fetch('/api/serial/status');
      const j = await r.json();
      setSerialStatus(j.open);
    } catch (_) {
      setSerialStatus(false);
    }
  }

  btnSerialToggle.addEventListener('click', async () => {
    const isOpen = serialStatus.classList.contains('connected');
    try {
      if (isOpen) {
        await fetch('/api/serial/close', { method: 'POST', headers: { 'Content-Type': 'application/json' } });
      } else {
        await fetch('/api/serial/open', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
      }
      await fetchSerialStatus();
      if (!isOpen) refreshState();
    } catch (e) {
      alert('시리얼 연결 실패: ' + e.message);
    }
  });

  async function refreshState() {
    try {
      const r = await fetch('/api/relay/state');
      const j = await r.json();
      if (j.ok && j.state && j.state.length === 4) {
        [1, 2, 3, 4].forEach((ch, i) => {
          const el = document.getElementById('state' + ch);
          if (!el) return;
          el.textContent = j.state[i] ? 'ON' : 'OFF';
          el.className = 'state ' + (j.state[i] ? 'on' : 'off');
        });
      }
    } catch (_) {}
  }

  document.querySelectorAll('.relay-card').forEach(function (card) {
    const ch = parseInt(card.dataset.ch, 10);
    card.querySelector('.on').addEventListener('click', async () => {
      try {
        const r = await fetch('/api/relay/on/' + ch, { method: 'POST' });
        const j = await r.json();
        if (j.ok) refreshState();
      } catch (e) { alert(e.message); }
    });
    card.querySelector('.off').addEventListener('click', async () => {
      try {
        const r = await fetch('/api/relay/off/' + ch, { method: 'POST' });
        const j = await r.json();
        if (j.ok) refreshState();
      } catch (e) { alert(e.message); }
    });
  });

  function renderSchedules(data) {
    [1, 2, 3, 4].forEach(ch => {
      const list = document.getElementById('list' + ch);
      if (!list) return;
      const arr = data.schedules && data.schedules[ch] ? data.schedules[ch] : [];
      list.innerHTML = arr.map((s, idx) =>
        '<li>' +
        '<span>' + s.on_time + ' ON → ' + s.off_time + ' OFF ' + (s.days && s.days !== 'daily' ? '(' + s.days + ')' : '') + '</span>' +
        '<span class="del" data-ch="' + ch + '" data-idx="' + idx + '">삭제</span>' +
        '</li>'
      );
      list.querySelectorAll('.del').forEach(span => {
        span.addEventListener('click', () => deleteSchedule(parseInt(span.dataset.ch, 10), parseInt(span.dataset.idx, 10)));
      });
    });
  }

  async function loadSchedules() {
    try {
      const r = await fetch('/api/schedules');
      const j = await r.json();
      if (j.ok) renderSchedules(j);
    } catch (_) {}
  }

  async function deleteSchedule(ch, index) {
    if (!confirm('이 스케줄을 삭제할까요?')) return;
    try {
      const r = await fetch('/api/schedules/' + ch + '/' + index, { method: 'DELETE' });
      const j = await r.json();
      if (j.ok) loadSchedules();
    } catch (e) { alert(e.message); }
  }

  function openModal(ch, index, item) {
    scheduleEdit = { channel: ch, index: index };
    modalCh.textContent = ch + 'ch';
    onTime.value = item ? item.on_time : '09:00';
    offTime.value = item ? item.off_time : '18:00';
    days.value = item && item.days ? item.days : 'daily';
    modal.classList.remove('hidden');
  }

  modalCancel.addEventListener('click', () => { modal.classList.add('hidden'); });
  modalSave.addEventListener('click', async () => {
    const ch = scheduleEdit.channel;
    const idx = scheduleEdit.index;
    const body = { on_time: onTime.value, off_time: offTime.value, days: days.value || 'daily' };
    try {
      if (idx === null) {
        const r = await fetch('/api/schedules', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ channel: ch, ...body }) });
        const j = await r.json();
        if (!j.ok) { alert(j.error || '추가 실패'); return; }
      } else {
        const r = await fetch('/api/schedules/' + ch + '/' + idx, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
        const j = await r.json();
        if (!j.ok) { alert(j.error || '수정 실패'); return; }
      }
      modal.classList.add('hidden');
      loadSchedules();
    } catch (e) { alert(e.message); }
  });

  document.querySelectorAll('.add-schedule').forEach(btn => {
    btn.addEventListener('click', () => {
      const ch = parseInt(btn.dataset.ch, 10);
      const list = document.getElementById('list' + ch);
      const count = list ? list.querySelectorAll('li').length : 0;
      if (count >= 10) { alert('채널당 최대 10개까지 가능합니다.'); return; }
      openModal(ch, null, null);
    });
  });

  fetchSerialStatus();
  loadSchedules();
  setInterval(refreshState, 3000);
})();
