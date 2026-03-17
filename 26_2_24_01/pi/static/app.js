(function () {
  const serialStatus = document.getElementById('serialStatus');
  const btnSerialToggle = document.getElementById('btnSerialToggle');
  const modal = document.getElementById('modal');
  const modalCh = document.getElementById('modalCh');
  const onTime = document.getElementById('onTime');
  const offTime = document.getElementById('offTime');
  const modalSave = document.getElementById('modalSave');
  const modalCancel = document.getElementById('modalCancel');
  const dayDaily = document.getElementById('dayDaily');
  const dayMon = document.getElementById('dayMon');
  const dayTue = document.getElementById('dayTue');
  const dayWed = document.getElementById('dayWed');
  const dayThu = document.getElementById('dayThu');
  const dayFri = document.getElementById('dayFri');
  const daySat = document.getElementById('daySat');
  const daySun = document.getElementById('daySun');

  let scheduleEdit = { channel: null, index: null };
  let lastScheduleData = { schedules: {} };
  const DAY_NAMES = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
  const selectedDayByCh = { 1: 'All', 2: 'All', 3: 'All', 4: 'All' };

  const dayCheckboxMap = {
    Mon: dayMon,
    Tue: dayTue,
    Wed: dayWed,
    Thu: dayThu,
    Fri: dayFri,
    Sat: daySat,
    Sun: daySun
  };

  function formatTime(t) {
    if (!t) return '00:00';
    const parts = String(t).trim().split(':');
    const h = parseInt(parts[0], 10);
    const m = parts.length > 1 ? parseInt(parts[1], 10) : 0;
    return (isNaN(h) ? '00' : String(h).padStart(2, '0')) + ':' + (isNaN(m) ? '00' : String(m).padStart(2, '0'));
  }

  function formatDays(days) {
    if (!days || days === 'daily') return 'daily';
    return String(days).split(',').map(function (p) {
      const x = p.trim();
      if (/^[0-6]$/.test(x)) return DAY_NAMES[parseInt(x, 10)];
      return x;
    }).join(',');
  }

  function scheduleMatchesDay(s, dayFilter) {
    if (dayFilter === 'All') return true;
    const d = (s && s.days) ? String(s.days).trim() : '';
    if (!d || d === 'daily') return true;
    const parts = d.split(',').map(function (p) { return p.trim(); });
    const dayIndex = DAY_NAMES.indexOf(dayFilter);
    for (let i = 0; i < parts.length; i++) {
      if (parts[i] === dayFilter) return true;
      if (parts[i] === String(dayIndex)) return true;
    }
    return false;
  }

  function setDayInputsFromDaysString(daysStr, ch) {
    // 기본: 모두 해제
    if (dayDaily) dayDaily.checked = false;
    DAY_NAMES.forEach(function (name) {
      const cb = dayCheckboxMap[name];
      if (cb) cb.checked = false;
    });
    const d = (daysStr && String(daysStr).trim()) || '';
    if (!d || d === 'daily') {
      if (dayDaily) dayDaily.checked = true;
      return;
    }
    const parts = d.split(',').map(function (p) { return p.trim(); }).filter(Boolean);
    parts.forEach(function (p) {
      let name = p;
      if (/^[0-6]$/.test(p)) {
        const idx = parseInt(p, 10);
        if (idx >= 0 && idx < DAY_NAMES.length) name = DAY_NAMES[idx];
      }
      const cb = dayCheckboxMap[name];
      if (cb) cb.checked = true;
    });
  }

  function getDaysStringFromInputs() {
    if (dayDaily && dayDaily.checked) {
      return 'daily';
    }
    const selected = DAY_NAMES.filter(function (name) {
      const cb = dayCheckboxMap[name];
      return cb && cb.checked;
    });
    if (!selected.length) {
      // 아무 것도 선택 안 한 경우 기본값: daily
      return 'daily';
    }
    return selected.join(',');
  }

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
    lastScheduleData = data || lastScheduleData;
    const schedules = lastScheduleData.schedules || {};
    [1, 2, 3, 4].forEach(ch => {
      const list = document.getElementById('list' + ch);
      if (!list) return;
      const fullArr = schedules[ch] || [];
      const dayFilter = selectedDayByCh[ch] || 'All';
      const filtered = fullArr.map(function (s, idx) { return { s: s, idx: idx }; }).filter(function (x) { return scheduleMatchesDay(x.s, dayFilter); });
      list.innerHTML = filtered.map(function (x) {
        const onT = formatTime(x.s.on_time);
        const offT = formatTime(x.s.off_time);
        const daysLabel = formatDays(x.s.days);
        return '<li>' +
          '<span>' + onT + ' ON → ' + offT + ' OFF ' + (daysLabel !== 'daily' ? '(' + daysLabel + ')' : '') + '</span>' +
          '<span class="del" data-ch="' + ch + '" data-idx="' + x.idx + '">삭제</span>' +
          '</li>';
      });
      list.querySelectorAll('.del').forEach(span => {
        span.addEventListener('click', () => deleteSchedule(parseInt(span.dataset.ch, 10), parseInt(span.dataset.idx, 10)));
      });
    });
  }

  async function loadSchedules() {
    try {
      const r = await fetch('/api/schedules');
      const j = await r.json();
      if (j.ok) {
        lastScheduleData = j;
        renderSchedules(j);
      }
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
    onTime.value = item ? formatTime(item.on_time) : '09:00';
    offTime.value = item ? formatTime(item.off_time) : '18:00';
    const baseDays = item && item.days
      ? item.days
      : (selectedDayByCh[ch] === 'All' ? 'daily' : selectedDayByCh[ch]);
    setDayInputsFromDaysString(baseDays, ch);
    modal.classList.remove('hidden');
  }

  modalCancel.addEventListener('click', () => { modal.classList.add('hidden'); });
  modalSave.addEventListener('click', async () => {
    const ch = scheduleEdit.channel;
    const idx = scheduleEdit.index;
    const daysVal = getDaysStringFromInputs();
    const body = { on_time: formatTime(onTime.value), off_time: formatTime(offTime.value), days: daysVal };
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
      const count = (lastScheduleData.schedules && lastScheduleData.schedules[ch]) ? lastScheduleData.schedules[ch].length : 0;
      if (count >= 20) { alert('채널당 최대 20개까지 가능합니다.'); return; }
      openModal(ch, null, null);
    });
  });

  document.querySelectorAll('.schedule-day-filters').forEach(container => {
    const ch = parseInt(container.dataset.ch, 10);
    container.querySelectorAll('.day-filter').forEach(btn => {
      btn.addEventListener('click', () => {
        const day = btn.dataset.day;
        selectedDayByCh[ch] = day;
        container.querySelectorAll('.day-filter').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        renderSchedules();
      });
    });
  });

  // 토양 센서 — 실시간값 / 7일 평균만 표시 (그래프 없음)
  function setBadgeEl(id, val) {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = val == null || (typeof val === 'number' && isNaN(val)) ? '-' : val;
  }

  async function refreshBadgeValues() {
    try {
      const r = await fetch('/api/badge/history?days=7&limit=3000');
      const j = await r.json();
      if (!j.ok || !j.history || !j.history.length) {
        ['Temp', 'Humi', 'EC', 'PH', 'N', 'P', 'K'].forEach((name) => {
          setBadgeEl('badge' + name + 'Current', null);
          setBadgeEl('badge' + name + 'Avg', null);
        });
        return;
      }
      const hist = j.history;
      const keys = [
        { cur: 'badgeTempCurrent', avg: 'badgeTempAvg', raw: 'soil_temperature' },
        { cur: 'badgeHumiCurrent', avg: 'badgeHumiAvg', raw: 'soil_humidity' },
        { cur: 'badgeECCurrent', avg: 'badgeECAvg', raw: 'soil_EC' },
        { cur: 'badgePHCurrent', avg: 'badgePHAvg', raw: 'soil_ph' },
        { cur: 'badgeNCurrent', avg: 'badgeNAvg', raw: 'soil_N' },
        { cur: 'badgePCurrent', avg: 'badgePAvg', raw: 'soil_P' },
        { cur: 'badgeKCurrent', avg: 'badgeKAvg', raw: 'soil_K' }
      ];
      const last = hist[hist.length - 1];
      let lastRaw = null;
      try {
        lastRaw = typeof last.raw === 'string' ? JSON.parse(last.raw) : last.raw;
      } catch (_) {}
      const sums = {};
      const counts = {};
      hist.forEach((d) => {
        try {
          const raw = typeof d.raw === 'string' ? JSON.parse(d.raw) : d.raw;
          if (raw && typeof raw === 'object') {
            keys.forEach((k) => {
              const v = raw[k.raw];
              if (v != null && !isNaN(Number(v))) {
                if (!sums[k.raw]) sums[k.raw] = 0;
                sums[k.raw] += Number(v);
                counts[k.raw] = (counts[k.raw] || 0) + 1;
              }
            });
          }
        } catch (_) {}
      });
      keys.forEach((k) => {
        const curVal = lastRaw && lastRaw[k.raw] != null ? Number(lastRaw[k.raw]) : null;
        const n = counts[k.raw] || 0;
        const avgVal = n > 0 && sums[k.raw] != null ? Math.round(sums[k.raw] / n * 10) / 10 : null;
        setBadgeEl(k.cur, curVal);
        setBadgeEl(k.avg, avgVal);
      });
    } catch (_) {}
  }
  setInterval(refreshBadgeValues, 5000);
  refreshBadgeValues();

  async function refreshCameraStatus() {
    try {
      const el = document.getElementById('cameraStatusText');
      const inputEl = document.getElementById('cameraDisplayInput');
      if (!el) return;
      const r = await fetch('/api/camera/status');
      const j = await r.json();
      if (!j.ok) {
        el.textContent = j.error || '카메라 상태 조회 실패';
        return;
      }
      if (j.data && j.source === 'status_file') {
        const d = j.data;
        const custom = (d.custom_message || '').trim();
        const autoMsg = d.message || JSON.stringify(d);
        el.textContent = custom || autoMsg;
        if (inputEl) inputEl.value = custom;
      } else if (j.source === 'files') {
        el.textContent = j.message || '마지막 촬영 파일 정보 없음';
        if (inputEl) inputEl.value = '';
      } else {
        el.textContent = j.message || '카메라 상태 정보가 없습니다.';
        if (inputEl) inputEl.value = '';
      }
    } catch (e) {
      const el = document.getElementById('cameraStatusText');
      if (el) el.textContent = '카메라 상태 조회 중 오류가 발생했습니다.';
    }
  }

  const cameraDisplaySave = document.getElementById('cameraDisplaySave');
  if (cameraDisplaySave) {
    cameraDisplaySave.addEventListener('click', async function () {
      const inputEl = document.getElementById('cameraDisplayInput');
      const msg = inputEl ? inputEl.value.trim() : '';
      try {
        const r = await fetch('/api/camera/display', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: msg })
        });
        const j = await r.json();
        if (j.ok) {
          refreshCameraStatus();
        } else {
          alert(j.error || '저장 실패');
        }
      } catch (e) {
        alert(e.message || '저장 중 오류');
      }
    });
  }

  refreshCameraStatus();
  setInterval(refreshCameraStatus, 60000);

  fetchSerialStatus();
  loadSchedules();
  setInterval(refreshState, 3000);
})();
