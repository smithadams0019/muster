// The console's only source of truth. It never prices a change or evaluates
// a rule itself — every action here is: call the API, refetch, render what
// came back. A console that reimplemented the policy could disagree with the
// agent, and the whole claim Muster makes is that it cannot.

import { create } from 'zustand'
import * as api from './api.js'

const OPERATOR = { by: 'Alex Smith', role: 'operator' }
const TOAST_MS = 4500

function emptyWorld() {
  return { now: null, sites: [], workers: [], jurisdictions: [] }
}

function ruleFor(decisions, decisionId, fallbackRule) {
  // The whole product's claim is that it names what stopped it in plain English
  // rather than in rule codes, and the toast is usually the first place an
  // operator reads that. It used to say "cost_over_budget"; the API already
  // returns the sentence, so use it and keep the code as a last resort.
  const decision = decisions.find((d) => d.decision_id === decisionId)
  const detail = decision?.rule_hits?.[0]?.detail
  if (detail) return detail
  return decision?.rule || fallbackRule || 'a policy limit'
}

export const useStore = create((set, get) => ({
  route: 'today',
  go: (route) => set({ route }),

  loading: true,
  error: null,
  busy: {},
  toast: null,

  world: emptyWorld(),
  decisions: [],
  consent: [],
  receipts: [],
  timeline: [],
  schedules: {},
  autonomy: { level: 'balanced', thresholds: {} },

  notify: (message) => {
    const ticket = Symbol('toast')
    set({ toast: message, _toastTicket: ticket })
    setTimeout(() => {
      if (get()._toastTicket === ticket) set({ toast: null })
    }, TOAST_MS)
  },

  refresh: async ({ quiet } = {}) => {
    if (!quiet) set({ loading: true })
    try {
      const [world, decisions, consent, receipts, timeline, autonomy] = await Promise.all([
        api.getWorld(),
        api.getDecisions(),
        api.getConsent(),
        api.getReceipts(),
        api.getTimeline(),
        api.getAutonomy(),
      ])

      const schedules = {}
      await Promise.all(
        (world.sites || []).map(async (site) => {
          try {
            schedules[site.site_id] = await api.getSchedule(site.site_id)
          } catch {
            schedules[site.site_id] = null
          }
        }),
      )

      set({
        world,
        decisions,
        consent,
        receipts,
        timeline,
        autonomy,
        schedules,
        loading: false,
        error: null,
      })
    } catch (err) {
      set({ loading: false, error: err?.message || 'Could not reach Muster' })
    }
  },

  reportDisruption: async ({ kind, shift_id, note }) => {
    const key = `disruption:${shift_id}`
    set((s) => ({ busy: { ...s.busy, [key]: true } }))
    try {
      const res = await api.reportDisruption({ kind, shift_id, note })
      await get().refresh({ quiet: true })

      if (res.status === 'awaiting_decision') {
        const rule = ruleFor(get().decisions, res.decision_id, res.rule)
        get().notify(`Held for you — ${rule}`)
        set({ route: 'decisions' })
      } else if (res.status === 'covered') {
        get().notify('Covered without interrupting you')
      } else {
        get().notify('Nobody could take it — nothing changed')
      }
      return res
    } catch (err) {
      get().notify(err?.message || 'Could not report the disruption')
      throw err
    } finally {
      set((s) => ({ busy: { ...s.busy, [key]: false } }))
    }
  },

  answerDecision: async (id, outcome, note = '') => {
    const key = `decision:${id}`
    set((s) => ({ busy: { ...s.busy, [key]: true } }))
    try {
      const res = await api.answerDecision(id, {
        outcome,
        by: OPERATOR.by,
        role: OPERATOR.role,
        note,
      })
      await get().refresh({ quiet: true })

      if (res.status === 'awaiting_decision') {
        const rule = ruleFor(get().decisions, res.decision_id, res.rule)
        get().notify(`Held for you — ${rule}`)
      } else if (res.status === 'covered') {
        get().notify('Approved — the shift is covered')
      } else if (res.status === 'declined') {
        // A decline is not handed back to the agent at all, so nothing about
        // anyone's week changed. Say that rather than implying Muster tried.
        get().notify('Declined — the shift is still open and nothing was changed')
      } else {
        get().notify('Nobody could take it — nothing changed')
      }
      return res
    } catch (err) {
      get().notify(err?.message || 'Could not record that decision')
      throw err
    } finally {
      set((s) => ({ busy: { ...s.busy, [key]: false } }))
    }
  },

  answerConsent: async (id, outcome) => {
    const key = `consent:${id}`
    set((s) => ({ busy: { ...s.busy, [key]: true } }))
    try {
      const res = await api.answerConsent(id, { outcome, channel: 'console' })
      await get().refresh({ quiet: true })

      // A grant sends Muster back to finish the cover it stopped to ask about,
      // so the answer here has the same three endings a disruption does. Saying
      // "Consent recorded" for all of them told the operator nothing about
      // whether the shift ended up covered.
      if (res.status === 'awaiting_decision') {
        const rule = ruleFor(get().decisions, res.decision_id, res.rule)
        get().notify(`Consent recorded — now held for you: ${rule}`)
        set({ route: 'decisions' })
      } else if (res.status === 'covered') {
        get().notify('Consent recorded — the shift is covered')
      } else if (res.status === 'declined') {
        get().notify('Decline recorded — Muster will not ask again')
      } else {
        get().notify('Consent recorded, but nobody could take the shift')
      }
      return res
    } catch (err) {
      get().notify(err?.message || 'Could not record consent')
      throw err
    } finally {
      set((s) => ({ busy: { ...s.busy, [key]: false } }))
    }
  },

  resetDemo: async () => {
    const key = 'reset'
    set((s) => ({ busy: { ...s.busy, [key]: true } }))
    try {
      await api.resetDemo()
      await get().refresh({ quiet: true })
      set({ route: 'schedule' })
      get().notify('World reset — back to the posted week')
    } catch (err) {
      get().notify(err?.message || 'Could not reset the world')
      throw err
    } finally {
      set((s) => ({ busy: { ...s.busy, [key]: false } }))
    }
  },

  setAutonomy: async (level) => {
    const key = 'autonomy'
    set((s) => ({ busy: { ...s.busy, [key]: true } }))
    try {
      const autonomy = await api.setAutonomy(level)
      set({ autonomy })
      get().notify(`Autonomy set to ${level}`)
      return autonomy
    } catch (err) {
      get().notify(err?.message || 'Could not change autonomy')
      throw err
    } finally {
      set((s) => ({ busy: { ...s.busy, [key]: false } }))
    }
  },

  draftWeek: async (siteId) => {
    const key = `draft:${siteId}`
    set((s) => ({ busy: { ...s.busy, [key]: true } }))
    try {
      const res = await api.draftWeek(siteId)
      await get().refresh({ quiet: true })

      if (res.status === 'awaiting_decision') {
        const rule = ruleFor(get().decisions, res.decision_id, res.rule)
        get().notify(`Held for you — ${rule}`)
        set({ route: 'decisions' })
      } else {
        get().notify('Week drafted')
      }
      return res
    } catch (err) {
      get().notify(err?.message || 'Could not draft the week')
      throw err
    } finally {
      set((s) => ({ busy: { ...s.busy, [key]: false } }))
    }
  },
}))
