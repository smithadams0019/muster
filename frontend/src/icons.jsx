// Inline SVG stroke icons. 22px, currentColor, 2px stroke — matches the nav's
// icon+label pills. Kept as plain functions so any screen or component can
// import exactly the glyphs it needs without pulling in an icon-font build.

const base = {
  width: 22,
  height: 22,
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 2,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
}

function Svg({ children, ...props }) {
  return (
    <svg {...base} {...props} aria-hidden="true" focusable="false">
      {children}
    </svg>
  )
}

export function IconToday(props) {
  return (
    <Svg {...props}>
      <path d="M3 11.5 12 4l9 7.5" />
      <path d="M5.5 10v9a1 1 0 0 0 1 1H9a1 1 0 0 0 1-1v-4a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1v4a1 1 0 0 0 1 1h2.5a1 1 0 0 0 1-1v-9" />
    </Svg>
  )
}

export function IconDecisions(props) {
  return (
    <Svg {...props}>
      <path d="M4 12V6a1 1 0 0 1 1-1h14a1 1 0 0 1 1 1v6" />
      <path d="M4 12h4.5l1.5 3h4l1.5-3H20" />
      <path d="M4 12v6a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-6" />
    </Svg>
  )
}

export function IconConsent(props) {
  return (
    <Svg {...props}>
      <path d="M12 3.5c2.2 1.4 4.4 2 6.5 2 .3 3.6-.2 9.4-6.5 15-6.3-5.6-6.8-11.4-6.5-15 2.1 0 4.3-.6 6.5-2Z" />
      <path d="m9 12.2 2 2 4-4.2" />
    </Svg>
  )
}

export function IconSchedule(props) {
  return (
    <Svg {...props}>
      <rect x="3.5" y="4.5" width="17" height="16" rx="2" />
      <path d="M3.5 9.5h17" />
      <path d="M8 3v3M16 3v3" />
      <path d="M8 14h2M14 14h2M8 17.5h2M14 17.5h2" />
    </Svg>
  )
}

export function IconTeam(props) {
  return (
    <Svg {...props}>
      <circle cx="9" cy="8" r="3" />
      <path d="M3.5 19c0-3 2.5-5 5.5-5s5.5 2 5.5 5" />
      <circle cx="17" cy="9" r="2.4" />
      <path d="M15.7 14.3c2.4.3 4.3 2.1 4.3 4.7" />
    </Svg>
  )
}

export function IconAutonomy(props) {
  return (
    <Svg {...props}>
      <path d="M4 7h9M17 7h3" />
      <circle cx="14" cy="7" r="2.3" />
      <path d="M4 14h3M11 14h9" />
      <circle cx="8" cy="14" r="2.3" />
      <path d="M4 21h9M17 21h3" />
      <circle cx="14" cy="21" r="2.3" />
    </Svg>
  )
}

export function IconTimeline(props) {
  return (
    <Svg {...props}>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M12 7.5V12l3 2" />
    </Svg>
  )
}

export function IconReceipts(props) {
  return (
    <Svg {...props}>
      <path d="M6 3.5h12v17l-2.5-1.6L13 20.5l-1-1.6-1 1.6-2.5-1.6L6 20.5Z" />
      <path d="M9 8h6M9 11.5h6M9 15h4" />
    </Svg>
  )
}

export function IconAlert(props) {
  return (
    <Svg {...props}>
      <path d="M10.6 4.2 2.9 18a1.6 1.6 0 0 0 1.4 2.4h15.4a1.6 1.6 0 0 0 1.4-2.4L13.4 4.2a1.6 1.6 0 0 0-2.8 0Z" />
      <path d="M12 10v4.2" />
      <path d="M12 17.3h.01" />
    </Svg>
  )
}

export function IconSearch(props) {
  return (
    <Svg {...props}>
      <circle cx="11" cy="11" r="7" />
      <path d="m21 21-4.3-4.3" />
    </Svg>
  )
}

export function IconClose(props) {
  return (
    <Svg {...props}>
      <path d="M6 6l12 12M18 6 6 18" />
    </Svg>
  )
}

export function IconMore(props) {
  return (
    <Svg {...props}>
      <circle cx="5" cy="12" r="1.4" fill="currentColor" stroke="none" />
      <circle cx="12" cy="12" r="1.4" fill="currentColor" stroke="none" />
      <circle cx="19" cy="12" r="1.4" fill="currentColor" stroke="none" />
    </Svg>
  )
}

export function IconCheck(props) {
  return (
    <Svg {...props}>
      <path d="m4.5 12.5 5 5 10-11" />
    </Svg>
  )
}

export function IconChevronDown(props) {
  return (
    <Svg {...props}>
      <path d="m6 9 6 6 6-6" />
    </Svg>
  )
}

export function IconDownload(props) {
  return (
    <Svg {...props}>
      <path d="M12 4v11" />
      <path d="m7 10.5 5 5 5-5" />
      <path d="M4.5 19h15" />
    </Svg>
  )
}
