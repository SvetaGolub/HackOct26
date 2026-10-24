const API_BASE_URL = '/api/v1';

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
    departments: ['Без отдела'],
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
      periodicity: 'monthly'
    },
    isTelegramModalOpen: false,
    telegramForm: { login: '', code: '' },
    telegramLinkDetails: null,
    planCurrency: 'RUB',
    recurringPayments: [],
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
    selectedDateISO: isoDate(new Date()),
    newRec: {
      description: '',
      department: 'Без отдела',
      employee: '',
      amount: '',
      currency: 'RUB',
      periodicity: 'monthly',
      status: 'В ожидании',
      paidAt: ''
    },
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
        this.apiRequest('/payments/summary')
      ];
      if (this.isAdmin) {
        requests.push(this.fetchAll('/audit-log'));
        requests.push(this.fetchAll('/users'));
      }
      const [recurringPayments, occurrences, summary, history, users] = await Promise.all(requests);
      this.recurringPayments = recurringPayments;
      this.paymentSummary = summary;
      const recurringById = Object.fromEntries(recurringPayments.map(item => [item.id, item]));
      this.records = occurrences.map(item => this.mapOccurrence(item, recurringById));
      this.paymentHistory = (history || []).map(item => this.mapAuditEntry(item));
      this.accounts = users || [this.currentUser];
      this.departments = ['Без отдела', ...new Set([
        ...this.records.map(item => item.department),
        ...recurringPayments.map(item => item.department)
      ].filter(item => item && item !== '—' && item !== 'Без отдела'))];
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
        periodicity: recurring?.periodicity === 'one_time' ? 'Разовый' : 'Ежемесячно',
        status,
        isOverdue: Boolean(item.overdue),
        isPaid: Boolean(item.is_paid),
        isDeleted: recurring ? !recurring.is_active : false
      };
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
        .reduce((total, item) => {
          if (item.periodicity === 'monthly') {
            return total + Number(item.amount) * (month === null ? 12 : 1);
          }
          const dueDate = new Date(`${item.first_due_date}T00:00:00`);
          return dueDate.getFullYear() === year && (month === null || dueDate.getMonth() === month)
            ? total + Number(item.amount)
            : total;
        }, 0);
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
      window.alert('Для смены пользователя выйдите из аккаунта и войдите под другой учётной записью.');
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

    getRecordsByDate(date) {
      return this.records.filter(record => record.dueDate === date);
    },

    isOverdue(item) {
      return Boolean(item.isOverdue)
        || (item.paidAt ? item.paidAt > item.dueDate : this.referenceTodayISO > item.dueDate);
    },

    hasTelegramReminderSoon(date) {
      const daysUntilDue = Math.round(
        (new Date(`${date}T00:00:00`) - new Date(`${this.referenceTodayISO}T00:00:00`)) / 86400000
      );
      return daysUntilDue >= 0 && daysUntilDue <= 3
        && this.getRecordsByDate(date).some(record => !record.isPaid);
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
      this.selectedDateISO = date;
      this.newRec.currency = 'RUB';
      this.newRec.paidAt = '';
      this.newRec.description = '';
      this.newRec.employee = '';
      this.newRec.amount = '';
      this.newRec.periodicity = 'monthly';
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

    addDepartment() {
      const department = this.newDeptName.trim();
      if (department && !this.departments.includes(department)) this.departments.push(department);
      if (department) this.newRec.department = department;
      this.newDeptName = '';
      this.showAddDeptInput = false;
    },

    async createRecord() {
      if (!this.isAdmin) return;
      const body = {
        title: this.newRec.description.trim(),
        amount: Number(this.newRec.amount),
        currency: this.newRec.currency,
        first_due_date: this.selectedDateISO,
        periodicity: this.newRec.periodicity,
        department: this.newRec.department.trim() || null,
        employee: this.newRec.employee.trim() || null
      };
      try {
        const recurring = await this.apiRequest('/recurring-payments', 'POST', body);
        if (this.newRec.status === 'Одобрено') {
          const occurrences = await this.apiRequest(
            `/payment-occurrences?date_from=${this.selectedDateISO}&date_to=${this.selectedDateISO}&limit=500`
          );
          const occurrence = occurrences.find(item => item.recurring_payment_id === recurring.id);
          if (!occurrence) throw new Error('Платёж создан, но его период не найден для отметки оплаты.');
          await this.apiRequest(`/payment-occurrences/${occurrence.id}`, 'PATCH', {
            is_paid: true,
            paid_date: this.newRec.paidAt || this.referenceTodayISO
          });
        }
        this.isModalOpen = false;
        await this.loadFromBackend();
      } catch (error) {
        this.showError(error);
        await this.loadFromBackend();
      }
    },

    async deleteRecord(occurrenceId) {
      if (!this.isAdmin) return;
      const record = this.records.find(item => item.id === occurrenceId);
      if (!record || !window.confirm('Прекратить регулярный платёж? История оплат сохранится.')) return;
      try {
        await this.apiRequest(`/recurring-payments/${record.recurringId}`, 'DELETE');
        await this.loadFromBackend();
      } catch (error) {
        this.showError(error);
      }
    },

    openFeedbackModal() {
      if (this.isAdmin) return;
      this.feedbackForm.employee = this.feedbackForm.employee || this.currentAccount.full_name || '';
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
          periodicity: feedback.periodicity
        });
        this.feedbackForm.request = '';
        this.feedbackForm.amount = '';
        this.isFeedbackModalOpen = false;
        window.alert('Обращение отправлено администратору.');
      } catch (error) {
        this.showError(error);
      }
    },

    async openTelegramModal() {
      this.telegramLinkDetails = null;
      this.telegramForm.login = '';
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
        this.telegramLinkDetails = await this.apiRequest('/auth/telegram-link', 'POST', {});
      } catch (error) {
        this.showError(error);
      }
    },

    async disconnectTelegram() {
      try {
        await this.apiRequest('/auth/telegram-link', 'DELETE');
        this.currentUser = await this.apiRequest('/auth/me');
        this.telegramLinkDetails = null;
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
