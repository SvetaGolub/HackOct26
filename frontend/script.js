const API_BASE_URL = '/api/v1';

// Периодичность: новый фронт работает с русскими подписями, API — с кодами.
const PERIODICITY_LABELS = {
  monthly: 'Ежемесячно',
  weekly: 'Еженедельно',
  yearly: 'Ежегодно',
  daily: 'Ежедневно',
  custom: 'Кастомная',
  one_time: 'Разовый платёж'
};

function periodicityToApi(value) {
  if (PERIODICITY_LABELS[value]) return value; // уже код API
  const found = Object.entries(PERIODICITY_LABELS).find(([, label]) => label === value);
  return found ? found[0] : 'monthly';
}

function periodicityToLabel(code) {
  return PERIODICITY_LABELS[code] || PERIODICITY_LABELS.monthly;
}

function formatDateTimeRu(value) {
  if (!value) return '';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return '';
  const p = n => String(n).padStart(2, '0');
  return `${p(d.getDate())}.${p(d.getMonth() + 1)}.${d.getFullYear()} ${p(d.getHours())}:${p(d.getMinutes())}`;
}

function isoDate(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function startOfCurrentWeek() {
  const date = new Date();
  date.setHours(0, 0, 0, 0);
  date.setDate(date.getDate() - ((date.getDay() + 6) % 7));
  return date;
}

function invoiceKeeperApp(pageRole = 'admin') {
  return {
    pageRole,
    theme: localStorage.getItem('app-theme') || 'light',
    weekdays: ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'],
    departments: JSON.parse(localStorage.getItem('ik-departments') || 'null') || ['Без отдела'],
    removedDepartments: JSON.parse(localStorage.getItem('ik-removed-departments') || '[]'),
    newDeptName: '',
    showAddDeptInput: false,
    isDeptMenuOpen: false,
    isFeedbackModalOpen: false,
    feedbackForm: {
      employee: '',
      department: '',
      request: '',
      amount: '',
      currency: 'RUB',
      dueDate: '',
      periodicity: 'Ежемесячно',
      intervalDays: 7,
      customDays: 7
    },
    isTelegramModalOpen: false,
    telegramForm: { code: '' },
    isFullCalendarOpen: false,
    calYear: new Date().getFullYear(),
    calMonth: new Date().getMonth(),
    jump: { day: 1, month: new Date().getMonth() + 1, year: new Date().getFullYear() },
    monthNames: ['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь', 'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'],
    planCurrency: 'RUB',
    recurringPayments: [],
    departmentRecords: [],
    paymentSummary: [],
    referenceTodayISO: isoDate(new Date()),
    startMonday: startOfCurrentWeek(),
    tableSearch: '',
    tableDeptFilter: '',
    tableStatusFilter: '',
    tableCurrencyFilter: '',
    showTableFilter: false,
    journalSearch: '',
    journalStatusFilter: '',
    isHistoryFilterOpen: false,
    isModalOpen: false,
    editingId: null,
    editingOriginalDate: '',
    selectedDateISO: isoDate(new Date()),
    newRec: {
      description: '',
      department: 'Без отдела',
      employee: '',
      amount: '',
      currency: 'RUB',
      periodicity: 'Ежемесячно',
      status: 'В ожидании',
      paidAt: '',
      receiptUrl: ''
    },
    customPeriodDays: 7,
    pendingReceipt: null,
    isAccountMenuOpen: false,
    isAddAccountModalOpen: false,
    addAccForm: { login: '', password: '' },
    loginForm: { login: '', password: '' },
    accounts: [],
    currentUser: null,
    records: [],
    paymentHistory: [],
    authToken: localStorage.getItem('invoice-keeper-token') || '',

    get currentAccount() {
      if (!this.currentUser) return {};
      return {
        ...this.currentUser,
        email: this.currentUser.login,
        fullName: this.currentUser.full_name || this.currentUser.login,
        label: this.currentUser.role === 'admin' ? 'Администратор' : 'Пользователь'
      };
    },

    get isAdmin() {
      return this.currentUser?.role === 'admin';
    },

    get telegramLinked() {
      return Boolean(this.currentUser?.telegram_id);
    },

    get telegramLogin() {
      return this.currentUser?.telegram_id ? String(this.currentUser.telegram_id) : '';
    },

    get currentMonthPlan() {
      return this.formatMoney(this.plannedAmount(new Date().getFullYear(), new Date().getMonth()), this.planCurrency);
    },

    get currentYearPlan() {
      return this.formatMoney(this.plannedAmount(new Date().getFullYear()), this.planCurrency);
    },

    get periodLabel() {
      const end = new Date(this.startMonday);
      end.setDate(end.getDate() + 13);
      const options = { month: 'long', year: 'numeric' };
      const startLabel = this.startMonday.toLocaleDateString('ru-RU', options);
      const endLabel = end.toLocaleDateString('ru-RU', options);
      return startLabel === endLabel ? startLabel : `${startLabel} — ${endLabel}`;
    },

    get calendarDays() {
      return Array.from({ length: 14 }, (_, index) => {
        const date = new Date(this.startMonday);
        date.setDate(date.getDate() + index);
        return {
          iso: isoDate(date),
          displayDate: date.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit' })
        };
      });
    },

    get fullCalendarCells() {
      const first = new Date(this.calYear, this.calMonth, 1);
      const offset = (first.getDay() + 6) % 7;
      const count = new Date(this.calYear, this.calMonth + 1, 0).getDate();
      const rangeEnd = new Date(this.startMonday);
      rangeEnd.setDate(rangeEnd.getDate() + 13);
      return [
        ...Array(offset).fill(null),
        ...Array.from({ length: count }, (_, index) => {
          const date = new Date(this.calYear, this.calMonth, index + 1);
          const iso = isoDate(date);
          return {
            day: index + 1,
            iso,
            weekend: date.getDay() === 0 || date.getDay() === 6,
            inRange: date >= this.startMonday && date <= rangeEnd,
            count: this.getRecordsByDate(iso).length
          };
        })
      ];
    },

    get filteredTableRecords() {
      const query = this.tableSearch.toLocaleLowerCase().trim();
      return this.records.filter(record => {
        const matchesQuery = !query || [
          record.description,
          record.department,
          record.employee
        ].some(value => String(value).toLocaleLowerCase().includes(query));
        return matchesQuery
          && (!this.tableDeptFilter || record.department === this.tableDeptFilter)
          && (!this.tableStatusFilter || record.status === this.tableStatusFilter)
          && (!this.tableCurrencyFilter || record.currency === this.tableCurrencyFilter);
      });
    },

    get filteredHistoryRecords() {
      const entries = this.isAdmin
        ? this.paymentHistory
        : this.records.map(record => ({
          ...record,
          action: record.status === 'Одобрено' ? 'Платёж оплачен' : 'Ожидает оплаты',
          timestamp: `Срок: ${this.formatReadableDate(record.dueDate)}`,
          actor: ''
        }));
      const query = this.journalSearch.toLocaleLowerCase().trim();
      return entries.filter(item => {
        const matchesQuery = !query || [
          item.description,
          item.department,
          item.employee,
          item.action,
          item.actor
        ].some(value => String(value || '').toLocaleLowerCase().includes(query));
        return matchesQuery && (!this.journalStatusFilter || item.status === this.journalStatusFilter);
      });
    },

    async apiRequest(path, method = 'GET', body = null) {
      const headers = {};
      if (body !== null) headers['Content-Type'] = 'application/json';
      if (this.authToken) headers.Authorization = `Bearer ${this.authToken}`;

      let response;
      try {
        response = await fetch(`${API_BASE_URL}${path}`, {
          method,
          headers,
          ...(body !== null ? { body: JSON.stringify(body) } : {})
        });
      } catch (error) {
        throw new Error(`Не удалось подключиться к API: ${error.message}`);
      }

      if (response.status === 204) return null;
      const contentType = response.headers.get('content-type') || '';
      const result = contentType.includes('application/json')
        ? await response.json()
        : await response.text();

      if (!response.ok) {
        const detail = result?.detail || result?.message || result;
        const message = Array.isArray(detail)
          ? detail.map(item => item.msg || JSON.stringify(item)).join('; ')
          : typeof detail === 'string' ? detail : JSON.stringify(detail);
        const error = new Error(`Ошибка API (${response.status}): ${message || response.statusText}`);
        error.status = response.status;
        throw error;
      }
      return result;
    },

    async fetchAll(path) {
      const items = [];
      const pageSize = 500;
      let offset = 0;
      let page;
      do {
        const separator = path.includes('?') ? '&' : '?';
        page = await this.apiRequest(`${path}${separator}limit=${pageSize}&offset=${offset}`);
        if (!Array.isArray(page)) throw new Error('API вернул неожиданный формат списка.');
        items.push(...page);
        offset += page.length;
      } while (page.length === pageSize);
      return items;
    },

    async init() {
      // Сброс режима редактирования при закрытии модалки, чтобы данные не «протекали» в создание
      this.$watch('isModalOpen', open => {
        if (!open && this.editingId !== null) {
          this.editingId = null;
          this.resetNewRec();
        }
      });

      if (this.pageRole === 'auth') {
        if (!this.authToken) return;
        try {
          this.currentUser = await this.apiRequest('/auth/me');
          this.navigateToRole();
        } catch (error) {
          if (error.status === 401) {
            this.clearSession();
            return;
          }
          this.showError(error);
        }
        return;
      }

      if (!this.authToken) {
        window.location.replace('auth.html');
        return;
      }
      try {
        this.currentUser = await this.apiRequest('/auth/me');
        if (this.currentUser.role !== this.pageRole) {
          this.navigateToRole();
          return;
        }
        await this.loadFromBackend();
      } catch (error) {
        if (error.status === 401) {
          this.clearSession();
          window.location.replace('auth.html');
          return;
        }
        this.showError(error);
      }
    },

    navigateToRole() {
      if (!this.currentUser) return;
      const page = this.currentUser.role === 'admin' ? 'admin.html' : 'user.html';
      if (this.pageRole !== 'auth' && window.location.pathname.endsWith(page)) return;
      window.location.replace(page);
    },

    async loadFromBackend() {
      const requests = [
        this.fetchAll('/recurring-payments?include_inactive=true'),
        this.fetchAll('/payment-occurrences'),
        this.apiRequest('/payments/summary'),
        this.fetchAll('/departments')
      ];
      if (this.isAdmin) {
        requests.push(this.fetchAll('/audit-log'));
        requests.push(this.fetchAll('/users'));
      }
      const [recurringPayments, occurrences, summary, departments, history, users] = await Promise.all(requests);
      this.recurringPayments = recurringPayments;
      this.departmentRecords = departments;
      this.paymentSummary = summary;
      const recurringById = Object.fromEntries(recurringPayments.map(item => [item.id, item]));
      this.records = occurrences.map(item => this.mapOccurrence(item, recurringById));
      if (this.isAdmin) {
        for (const recurring of recurringPayments.filter(item => !item.is_active)) {
          if (this.records.some(record => record.recurringId === recurring.id)) continue;
          this.records.push({
            id: `deleted-${recurring.id}`,
            recurringId: recurring.id,
            dueDate: recurring.first_due_date,
            paidAt: '',
            employee: recurring.employee || '—',
            department: recurring.department || 'Без отдела',
            description: recurring.title,
            amount: Number(recurring.amount),
            currency: recurring.currency,
            periodicity: this.formatPeriodicity(recurring),
            status: 'В ожидании',
            isOverdue: false,
            isPaid: false,
            isDeleted: true,
            isSynthetic: true,
            receiptName: '',
            receiptUrl: '',
            createdAt: formatDateTimeRu(recurring.created_at),
            receiptDataUrl: ''
          });
        }
      }
      this.paymentHistory = (history || []).map(item => this.mapAuditEntry(item));
      this.accounts = users || [this.currentUser];
      this.departments = ['Без отдела', ...departments.map(item => item.name)];
      if (!this.departments.includes(this.newRec.department)) this.newRec.department = this.departments[0];
      if (!this.newRec.department && this.departments.length) {
        this.newRec.department = this.departments[0];
      }
    },

    mapOccurrence(item, recurringById) {
      const recurring = recurringById[item.recurring_payment_id];
      const status = item.is_paid ? 'Одобрено' : item.overdue ? 'Отказано' : 'В ожидании';
      return {
        id: item.id,
        recurringId: item.recurring_payment_id,
        dueDate: item.due_date,
        paidAt: item.paid_date || '',
        employee: item.employee || recurring?.employee || '—',
        department: item.department || recurring?.department || 'Без отдела',
        description: item.title,
        amount: Number(item.amount),
        currency: item.currency,
        periodicity: this.formatPeriodicity(recurring),
        status,
        isOverdue: Boolean(item.overdue),
        isPaid: Boolean(item.is_paid),
        isDeleted: recurring ? !recurring.is_active : false,
        receiptName: item.receipt_name || '',
        receiptUrl: item.receipt_name || '',
        createdAt: formatDateTimeRu(item.created_at),
        reminderSent: Boolean(item.reminder_sent)
      };
    },

    formatPeriodicity(recurring) {
      if (!recurring) return 'Ежемесячно';
      const labels = {
        monthly: 'Ежемесячно',
        one_time: 'Разовый',
        daily: 'Ежедневно',
        weekly: 'Еженедельно',
        yearly: 'Ежегодно'
      };
      return recurring.periodicity === 'custom'
        ? `Каждые ${recurring.interval_days} дн.`
        : labels[recurring.periodicity] || recurring.periodicity;
    },

    mapAuditEntry(item) {
      const oldValue = item.old_value || {};
      const newValue = item.new_value || {};
      const value = { ...oldValue, ...newValue };
      const isPaid = value.is_paid ?? value.status === 'paid';
      const isOverdue = value.overdue === true;
      return {
        id: item.id,
        timestamp: new Date(item.created_at).toLocaleString('ru-RU'),
        action: item.action,
        employee: value.employee || '—',
        actor: item.actor_login || '—',
        department: value.department || '—',
        description: value.request || value.title || `${item.entity_type} #${item.entity_id}`,
        amount: Number(value.amount || 0),
        currency: value.currency || 'RUB',
        status: item.entity_type === 'feedback'
          ? 'В ожидании'
          : isPaid ? 'Одобрено' : isOverdue ? 'Отказано' : 'В ожидании'
      };
    },

    plannedAmount(year, month = null) {
      return this.recurringPayments
        .filter(item => item.is_active && item.currency === this.planCurrency)
        .reduce((total, item) => total + Number(item.amount) * this.countOccurrences(item, year, month), 0);
    },

    countOccurrences(recurring, year, month) {
      const from = new Date(year, month === null ? 0 : month, 1);
      const to = month === null ? new Date(year + 1, 0, 1) : new Date(year, month + 1, 1);
      const start = new Date(`${recurring.first_due_date}T00:00:00`);
      if (recurring.periodicity === 'one_time') return start >= from && start < to ? 1 : 0;
      if (recurring.periodicity === 'monthly') {
        let count = 0;
        let due = start;
        while (due < to) {
          if (due >= from) count += 1;
          const nextMonth = new Date(due.getFullYear(), due.getMonth() + 1, 1);
          due = new Date(
            nextMonth.getFullYear(),
            nextMonth.getMonth(),
            Math.min(start.getDate(), new Date(nextMonth.getFullYear(), nextMonth.getMonth() + 1, 0).getDate())
          );
        }
        return count;
      }
      if (recurring.periodicity === 'yearly') {
        let count = 0;
        let due = start;
        while (due < from) {
          const nextYear = due.getFullYear() + 1;
          due = new Date(nextYear, start.getMonth(), Math.min(
            start.getDate(),
            new Date(nextYear, start.getMonth() + 1, 0).getDate()
          ));
        }
        while (due < to) {
          count += 1;
          const nextYear = due.getFullYear() + 1;
          due = new Date(nextYear, start.getMonth(), Math.min(
            start.getDate(),
            new Date(nextYear, start.getMonth() + 1, 0).getDate()
          ));
        }
        return count;
      }
      const interval = recurring.periodicity === 'daily' ? 1
        : recurring.periodicity === 'weekly' ? 7 : Number(recurring.interval_days);
      if (!interval) return 0;
      const step = interval * 86400000;
      let due = start;
      if (due < from) due = new Date(due.getTime() + Math.ceil((from - due) / step) * step);
      return due >= to ? 0 : Math.ceil((to - due) / step);
    },

    async submitLoginPage() {
      const login = this.loginForm.login.trim();
      const password = this.loginForm.password;
      if (!login || !password) return;
      try {
        const result = await this.apiRequest('/auth/login', 'POST', { login, password });
        if (!result?.accessToken || !result.user) throw new Error('API вернул неполный ответ авторизации.');
        this.authToken = result.accessToken;
        this.currentUser = result.user;
        localStorage.setItem('invoice-keeper-token', this.authToken);
        this.navigateToRole();
      } catch (error) {
        this.showError(error);
      }
    },

    openAddAccountModal() {
      if (!this.isAdmin) return;
      this.isAccountMenuOpen = false;
      this.addAccForm.login = '';
      this.addAccForm.password = '';
      this.isAddAccountModalOpen = true;
    },

    async submitAddAccount() {
      if (!this.isAdmin) return;
      try {
        await this.apiRequest('/users', 'POST', {
          login: this.addAccForm.login.trim(),
          password: this.addAccForm.password
        });
        this.isAddAccountModalOpen = false;
        await this.loadFromBackend();
      } catch (error) {
        this.showError(error);
      }
    },

    switchAccount() {
      this.logoutAccount();
    },

    async logoutAccount() {
      this.isAccountMenuOpen = false;
      try {
        if (this.authToken) await this.apiRequest('/auth/logout', 'POST');
      } catch (error) {
        this.showError(error);
      } finally {
        this.clearSession();
        window.location.replace('auth.html');
      }
    },

    clearSession() {
      this.authToken = '';
      this.currentUser = null;
      localStorage.removeItem('invoice-keeper-token');
    },

    showError(error) {
      console.error('Ошибка Invoice Keeper:', error);
      window.alert(error.message || 'Не удалось выполнить запрос.');
    },

    toggleTheme() {
      this.theme = this.theme === 'light' ? 'dark' : 'light';
      localStorage.setItem('app-theme', this.theme);
    },

    shiftWeeks(days) {
      const next = new Date(this.startMonday);
      next.setDate(next.getDate() + days);
      this.startMonday = next;
    },

    openFullCalendar() {
      this.calYear = this.startMonday.getFullYear();
      this.calMonth = this.startMonday.getMonth();
      this.jump = { day: this.startMonday.getDate(), month: this.calMonth + 1, year: this.calYear };
      this.isFullCalendarOpen = true;
    },

    shiftCalMonth(delta) {
      const date = new Date(this.calYear, this.calMonth + delta, 1);
      this.calYear = date.getFullYear();
      this.calMonth = date.getMonth();
    },

    pickCalendarDate(iso) {
      const date = new Date(`${iso}T00:00:00`);
      date.setDate(date.getDate() - ((date.getDay() + 6) % 7));
      this.startMonday = date;
      this.selectedDateISO = iso;
      this.isFullCalendarOpen = false;
    },

    applyDateJump() {
      const date = new Date(this.jump.year, this.jump.month - 1, this.jump.day);
      if (date.getFullYear() !== this.jump.year || date.getMonth() !== this.jump.month - 1 || date.getDate() !== this.jump.day) {
        window.alert('Введите корректную дату.');
        return;
      }
      this.calYear = date.getFullYear();
      this.calMonth = date.getMonth();
      this.pickCalendarDate(isoDate(date));
    },

    getRecordsByDate(date) {
      return this.records.filter(record => record.dueDate === date);
    },

    isOverdue(item) {
      return Boolean(item.isOverdue)
        || (item.paidAt ? item.paidAt > item.dueDate : this.referenceTodayISO > item.dueDate);
    },

    hasTelegramReminderSoon(date) {
      return this.getRecordsByDate(date).some(record => record.reminderSent);
    },

    async onStatusChange(item) {
      if (item.status === 'Отказано') {
        item.status = item.isPaid ? 'Одобрено' : 'В ожидании';
        window.alert('Просрочка рассчитывается автоматически. API позволяет отметить платёж оплаченным или неоплаченным.');
        return;
      }
      const isPaid = item.status === 'Одобрено';
      await this.updateOccurrence(item, isPaid
        ? { is_paid: true, paid_date: item.paidAt || this.referenceTodayISO }
        : { is_paid: false });
    },

    async onActualDateChange(item) {
      await this.updateOccurrence(item, item.paidAt
        ? { is_paid: true, paid_date: item.paidAt }
        : { is_paid: false });
    },

    async updateOccurrence(item, payload) {
      try {
        const result = await this.apiRequest(`/payment-occurrences/${item.id}`, 'PATCH', payload);
        const recurringById = Object.fromEntries(this.recurringPayments.map(record => [record.id, record]));
        Object.assign(item, this.mapOccurrence(result, recurringById));
        await this.loadSummary();
      } catch (error) {
        this.showError(error);
        await this.loadFromBackend();
      }
    },

    async loadSummary() {
      this.paymentSummary = await this.apiRequest('/payments/summary');
    },

    getDayTotalsString(date) {
      const totals = {};
      this.getRecordsByDate(date).forEach(record => {
        totals[record.currency] = (totals[record.currency] || 0) + Number(record.amount);
      });
      return Object.entries(totals)
        .map(([currency, amount]) => `${amount.toLocaleString('ru-RU')} ${this.currencySymbol(currency)}`)
        .join(' | ');
    },

    setHistoryFilter(status) {
      this.journalStatusFilter = status;
      this.isHistoryFilterOpen = false;
    },

    resetTableFilters() {
      this.tableSearch = '';
      this.tableDeptFilter = '';
      this.tableStatusFilter = '';
      this.tableCurrencyFilter = '';
    },

    openDayModal(date) {
      this.editingId = null;
      this.editingOriginalDate = '';
      this.selectedDateISO = date;
      this.newRec.currency = 'RUB';
      this.newRec.paidAt = '';
      this.newRec.description = '';
      this.newRec.employee = '';
      this.newRec.amount = '';
      this.newRec.periodicity = 'Ежемесячно';
      this.newRec.receiptUrl = '';
      this.pendingReceipt = null;
      this.customPeriodDays = 7;
      this.newRec.status = 'В ожидании';
      this.isDeptMenuOpen = false;
      this.showAddDeptInput = false;
      this.isModalOpen = true;
    },

    toggleAddDepartment() {
      this.showAddDeptInput = !this.showAddDeptInput;
      this.isDeptMenuOpen = false;
      if (!this.showAddDeptInput) this.newDeptName = '';
    },

    async addDepartment() {
      const department = this.newDeptName.trim();
      if (!department) return;
      try {
        const created = await this.apiRequest('/departments', 'POST', { name: department });
        this.departmentRecords.push(created);
        this.departments = ['Без отдела', ...this.departmentRecords.map(item => item.name)];
        this.newRec.department = created.name;
      } catch (error) {
        this.showError(error);
      }
      this.newDeptName = '';
      this.showAddDeptInput = false;
    },

    async removeDepartment(department) {
      if (!department || department === 'Без отдела' || this.departments.length <= 1) return;
      if (!window.confirm(`Удалить отдел «${department}» из общего списка? Уже созданные платежи не изменятся.`)) return;
      const row = this.departmentRecords.find(item => item.name === department);
      if (!row) return;
      try {
        await this.apiRequest(`/departments/${row.id}`, 'DELETE');
        this.departmentRecords = this.departmentRecords.filter(item => item.id !== row.id);
        this.departments = ['Без отдела', ...this.departmentRecords.map(item => item.name)];
      } catch (error) {
        this.showError(error);
      }
      if (this.newRec.department === department) this.newRec.department = this.departments[0] || 'Без отдела';
    },

    async createRecord() {
      if (!this.isAdmin) return;
      const body = {
        title: this.newRec.description.trim(),
        amount: Number(this.newRec.amount),
        currency: this.newRec.currency,
        first_due_date: this.selectedDateISO,
        periodicity: periodicityToApi(this.newRec.periodicity),
        interval_days: periodicityToApi(this.newRec.periodicity) === 'custom' ? Number(this.customPeriodDays) : null,
        department: this.newRec.department.trim() || null,
        employee: this.newRec.employee.trim() || null
      };
      try {
        const recurring = await this.apiRequest('/recurring-payments', 'POST', body);
        const needsPaid = this.newRec.status === 'Одобрено';
        if (needsPaid || this.pendingReceipt) {
          const occurrences = await this.apiRequest(
            `/payment-occurrences?date_from=${this.selectedDateISO}&date_to=${this.selectedDateISO}&limit=500`
          );
          const occurrence = occurrences.find(item => item.recurring_payment_id === recurring.id);
          if (!occurrence) throw new Error('Платёж создан, но его период не найден для отметки оплаты или чека.');
          const patch = {};
          if (needsPaid) {
            patch.is_paid = true;
            patch.paid_date = this.newRec.paidAt || this.referenceTodayISO;
          }
          if (this.pendingReceipt) {
            patch.receipt_name = this.pendingReceipt.name;
            patch.receipt_data_url = this.pendingReceipt.dataUrl;
          }
          await this.apiRequest(`/payment-occurrences/${occurrence.id}`, 'PATCH', patch);
        }
        this.pendingReceipt = null;
        this.isModalOpen = false;
        this.editingId = null;
        await this.loadFromBackend();
      } catch (error) {
        this.showError(error);
        await this.loadFromBackend();
      }
    },

    async deleteRecord(occurrenceId) {
      if (!this.isAdmin) return false;
      const record = this.records.find(item => item.id === occurrenceId);
      if (!record || !window.confirm('Прекратить регулярный платёж? История оплат сохранится.')) return false;
      try {
        await this.apiRequest(`/recurring-payments/${record.recurringId}`, 'DELETE');
        await this.loadFromBackend();
        return true;
      } catch (error) {
        this.showError(error);
        return false;
      }
    },

    async restoreRecord(occurrenceId) {
      if (!this.isAdmin) return;
      const record = this.records.find(item => item.id === occurrenceId);
      if (!record || !record.isDeleted) return;
      try {
        await this.apiRequest(`/recurring-payments/${record.recurringId}/restore`, 'POST');
        this.isModalOpen = false;
        await this.loadFromBackend();
      } catch (error) {
        this.showError(error);
      }
    },

    openEditModal(record) {
      if (!this.isAdmin || record.isDeleted) return;
      this.editingId = record.id;
      this.editingOriginalDate = record.dueDate;
      this.selectedDateISO = record.dueDate;
      this.newRec = {
        description: record.description,
        department: record.department,
        employee: record.employee === '—' ? '' : record.employee,
        amount: String(record.amount),
        currency: record.currency,
        periodicity: periodicityToLabel(this.recurringPayments.find(item => item.id === record.recurringId)?.periodicity),
        status: record.status,
        paidAt: record.paidAt || '',
        receiptUrl: record.receiptName || ''
      };
      this.pendingReceipt = null;
      this.customPeriodDays = this.recurringPayments.find(item => item.id === record.recurringId)?.interval_days || 7;
      this.isModalOpen = true;
    },

    resetNewRec() {
      this.editingId = null;
      this.pendingReceipt = null;
      this.customPeriodDays = 7;
      this.newRec = {
        description: '',
        department: this.departments[0] || 'Без отдела',
        employee: '',
        amount: '',
        currency: 'RUB',
        periodicity: 'Ежемесячно',
        status: 'В ожидании',
        paidAt: '',
        receiptUrl: ''
      };
    },

    isEditingDeleted() {
      return Boolean(this.records.find(item => item.id === this.editingId)?.isDeleted);
    },

    async saveEditedRecord() {
      if (!this.isAdmin || this.editingId === null) return;
      const record = this.records.find(item => item.id === this.editingId);
      if (!record || record.isDeleted) return;
      try {
        const payload = {
          title: this.newRec.description.trim(),
          amount: Number(this.newRec.amount),
          currency: this.newRec.currency,
          periodicity: periodicityToApi(this.newRec.periodicity),
          interval_days: periodicityToApi(this.newRec.periodicity) === 'custom' ? Number(this.customPeriodDays) : null,
          department: this.newRec.department.trim() || null,
          employee: this.newRec.employee.trim() || null
        };
        if (this.selectedDateISO !== this.editingOriginalDate) {
          payload.first_due_date = this.selectedDateISO;
        }
        await this.apiRequest(`/recurring-payments/${record.recurringId}`, 'PATCH', payload);
        if (this.newRec.status === 'Одобрено') {
          await this.apiRequest(`/payment-occurrences/${record.id}`, 'PATCH', {
            is_paid: true,
            paid_date: this.newRec.paidAt || this.referenceTodayISO
          });
        } else if (record.isPaid) {
          await this.apiRequest(`/payment-occurrences/${record.id}`, 'PATCH', { is_paid: false });
        }
        this.isModalOpen = false;
        this.editingId = null;
        this.editingOriginalDate = '';
        await this.loadFromBackend();
      } catch (error) {
        this.showError(error);
        await this.loadFromBackend();
      }
    },

    async deleteEditedRecord() {
      if (await this.deleteRecord(this.editingId)) this.isModalOpen = false;
    },

    async restoreEditedRecord() {
      await this.restoreRecord(this.editingId);
    },

    async handleFileUpload(event) {
      const file = event.target.files?.[0];
      if (!file) return;
      if (this.editingId !== null && this.isEditingDeleted()) {
        window.alert('Нельзя прикрепить чек к прекращённому платежу.');
        event.target.value = '';
        return;
      }
      if (!['image/png', 'image/jpeg', 'image/webp', 'application/pdf'].includes(file.type)) {
        window.alert('Можно прикрепить PNG, JPEG, WEBP или PDF.');
        event.target.value = '';
        return;
      }
      if (file.size > 2 * 1024 * 1024) {
        window.alert('Размер файла должен быть не больше 2 МБ.');
        event.target.value = '';
        return;
      }
      try {
        const receiptDataUrl = await new Promise((resolve, reject) => {
          const reader = new FileReader();
          reader.onload = () => resolve(reader.result);
          reader.onerror = () => reject(new Error('Не удалось прочитать файл.'));
          reader.readAsDataURL(file);
        });
        if (this.editingId === null) {
          // Платёж ещё не создан: чек прикрепится к первой оплате при создании
          this.pendingReceipt = { name: file.name, dataUrl: receiptDataUrl };
          this.newRec.receiptUrl = file.name;
          return;
        }
        await this.apiRequest(`/payment-occurrences/${this.editingId}`, 'PATCH', {
          receipt_name: file.name,
          receipt_data_url: receiptDataUrl
        });
        await this.loadFromBackend();
      } catch (error) {
        this.showError(error);
      } finally {
        event.target.value = '';
      }
    },

    async handleRecordFileUpload(event, item) {
      this.editingId = item.id;
      await this.handleFileUpload(event);
    },

    async downloadReceipt(item) {
      try {
        const receipt = await this.apiRequest(`/payment-occurrences/${item.id}/receipt`);
        const blob = await (await fetch(receipt.data_url)).blob();
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = receipt.name;
        document.body.appendChild(link);
        link.click();
        link.remove();
        window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
      } catch (error) {
        this.showError(error);
      }
    },

    async removeReceipt(item) {
      if (!window.confirm(`Удалить файл «${item.receiptName}»?`)) return;
      try {
        await this.apiRequest(`/payment-occurrences/${item.id}`, 'PATCH', {
          receipt_name: null,
          receipt_data_url: null
        });
        await this.loadFromBackend();
      } catch (error) {
        this.showError(error);
      }
    },

    openFeedbackModal() {
      if (this.isAdmin) return;
      this.feedbackForm.employee = this.feedbackForm.employee || this.currentAccount.fullName || '';
      this.feedbackForm.department = this.feedbackForm.department || 'Без отдела';
      this.feedbackForm.dueDate = this.feedbackForm.dueDate || this.referenceTodayISO;
      this.isFeedbackModalOpen = true;
    },

    async submitFeedback() {
      const feedback = this.feedbackForm;
      try {
        await this.apiRequest('/feedback', 'POST', {
          employee: feedback.employee.trim(),
          department: feedback.department.trim(),
          request: feedback.request.trim(),
          amount: Number(feedback.amount),
          currency: feedback.currency,
          due_date: feedback.dueDate,
          periodicity: periodicityToApi(feedback.periodicity),
          interval_days: periodicityToApi(feedback.periodicity) === 'custom' ? Number(feedback.customDays || feedback.intervalDays) : null
        });
        this.feedbackForm.request = '';
        this.feedbackForm.amount = '';
        this.isFeedbackModalOpen = false;
        window.alert('Обращение отправлено администратору в Telegram.');
      } catch (error) {
        this.showError(error);
      }
    },

    async openTelegramModal() {
      this.telegramForm.code = '';
      this.isTelegramModalOpen = true;
      try {
        this.currentUser = await this.apiRequest('/auth/me');
      } catch (error) {
        this.showError(error);
      }
    },

    async submitTelegram() {
      try {
        await this.apiRequest('/auth/telegram-link', 'POST', {
          code: this.telegramForm.code.trim().toUpperCase()
        });
        this.telegramForm.code = '';
        this.currentUser = await this.apiRequest('/auth/me');
        window.alert('Telegram успешно привязан.');
      } catch (error) {
        this.showError(error);
      }
    },

    async disconnectTelegram() {
      try {
        await this.apiRequest('/auth/telegram-link', 'DELETE');
        this.currentUser = await this.apiRequest('/auth/me');
      } catch (error) {
        this.showError(error);
      }
    },

    statusColor(item) {
      if (item.isDeleted) return 'deleted-gray';
      if (this.isOverdue(item) || item.status === 'Отказано') return 'rejected';
      if (item.status === 'Одобрено') return 'approved';
      return 'pending';
    },

    currencySymbol(code) {
      if (code === 'USD') return '$';
      if (code === 'EUR') return '€';
      return '₽';
    },

    formatMoney(amount, currency) {
      return `${Number(amount || 0).toLocaleString('ru-RU')} ${this.currencySymbol(currency || this.planCurrency)}`;
    },

    formatReadableDate(value) {
      if (!value) return '';
      const [year, month, day] = value.split('-');
      return `${day}.${month}.${year}`;
    }
  };
}