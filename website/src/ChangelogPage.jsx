import React, { useState } from 'react'
import { History, Plus, RefreshCw, Wrench } from 'lucide-react'
import { CHANGELOG, CURRENT_VERSION } from './changelog'

const LEGACY_README_URL =
  'https://github.com/lsk0522/AI_vision_tracker/blob/main/docs/versions/README_v2.1.0.md'
const CHANGELOG_URL = 'https://github.com/lsk0522/AI_vision_tracker/blob/main/docs/CHANGELOG.md'

export default function ChangelogPage() {
  const [selected, setSelected] = useState(CHANGELOG[0].version)
  const entry = CHANGELOG.find((c) => c.version === selected) ?? CHANGELOG[0]

  return (
    <div className="min-h-screen bg-brand-light text-brand-text font-sans overflow-x-hidden">
      <nav className="fixed w-full z-50 glass-panel border-b border-brand-border/30 px-4 md:px-6 py-4 flex justify-between items-center gap-3">
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-9 h-9 shrink-0 rounded-full bg-brand-neon/20 border border-brand-neon/50 flex items-center justify-center neon-glow">
            <History size={18} className="text-brand-neon" />
          </div>
          <span className="font-bold text-lg tracking-tight text-white truncate">바뀐점</span>
        </div>
        <button
          onClick={() => (window.location.hash = '')}
          className="shrink-0 px-4 md:px-6 py-2 rounded-full glass-panel text-white font-medium hover:bg-white/10 transition-colors border border-brand-border text-sm md:text-base"
        >
          ← 메인 화면
        </button>
      </nav>

      <main className="pt-28 pb-20 px-4 md:px-8 max-w-6xl mx-auto">
        <header className="mb-10">
          <h1 className="text-3xl md:text-5xl font-extrabold tracking-tight">버전별 바뀐점</h1>
          <p className="mt-4 text-brand-muted text-base md:text-lg leading-relaxed break-keep">
            지금 버전은 <strong className="text-brand-neon">{CURRENT_VERSION}</strong> 입니다. 지난 버전 기록은 지우지 않고
            여기에 모아 둡니다.
          </p>
        </header>

        <div className="flex flex-col md:flex-row gap-6 md:gap-10">
          {/* 버전 탭 */}
          <div
            role="tablist"
            aria-label="버전 목록"
            className="flex md:flex-col gap-2 overflow-x-auto md:overflow-visible pb-2 md:pb-0 md:w-56 shrink-0 -mx-4 px-4 md:mx-0 md:px-0"
          >
            {CHANGELOG.map((c) => {
              const active = c.version === selected
              return (
                <button
                  key={c.version}
                  role="tab"
                  aria-selected={active}
                  onClick={() => setSelected(c.version)}
                  className={`shrink-0 text-left rounded-2xl px-4 py-3 border transition-colors ${
                    active
                      ? 'bg-brand-neon/10 border-brand-neon/60 text-white'
                      : 'glass-panel border-brand-border/50 text-brand-muted hover:text-white hover:border-brand-border'
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <span className="font-mono font-bold">{c.version}</span>
                    {c.version === CURRENT_VERSION && (
                      <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-brand-neon text-brand-light">
                        현재
                      </span>
                    )}
                  </div>
                  <div className="text-xs mt-1 opacity-80 font-mono">{c.date}</div>
                </button>
              )
            })}
          </div>

          {/* 선택한 버전 내용 */}
          <section role="tabpanel" className="flex-1 min-w-0 glass-panel rounded-3xl p-6 md:p-10 border border-brand-border/50">
            <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
              <h2 className="text-2xl md:text-3xl font-extrabold text-white">{entry.version}</h2>
              <span className="font-mono text-sm text-brand-muted">{entry.date}</span>
            </div>
            <h3 className="mt-2 text-lg md:text-xl font-bold text-brand-neon break-keep">{entry.title}</h3>
            <p className="mt-4 text-brand-muted leading-relaxed break-keep">{entry.summary}</p>

            <ChangeGroup icon={<Plus size={16} />} label="추가" items={entry.added} />
            <ChangeGroup icon={<RefreshCw size={16} />} label="변경" items={entry.changed} />
            <ChangeGroup icon={<Wrench size={16} />} label="수정" items={entry.fixed} />
          </section>
        </div>

        <div className="mt-10 text-sm text-brand-muted leading-relaxed break-keep">
          자세한 기록:{' '}
          <a href={CHANGELOG_URL} target="_blank" rel="noreferrer" className="text-white underline underline-offset-4 hover:text-brand-neon">
            CHANGELOG.md
          </a>
          {' · '}
          v2.1.0 까지의 README 원본:{' '}
          <a href={LEGACY_README_URL} target="_blank" rel="noreferrer" className="text-white underline underline-offset-4 hover:text-brand-neon">
            README_v2.1.0.md
          </a>
        </div>
      </main>
    </div>
  )
}

function ChangeGroup({ icon, label, items }) {
  if (!items || items.length === 0) return null
  return (
    <div className="mt-8">
      <h4 className="flex items-center gap-2 text-sm font-bold text-white uppercase tracking-wide">
        <span className="w-7 h-7 rounded-lg bg-brand-surface border border-brand-border flex items-center justify-center text-brand-neon">
          {icon}
        </span>
        {label}
      </h4>
      <ul className="mt-3 space-y-2">
        {items.map((item, i) => (
          <li key={i} className="flex gap-3 text-brand-text/90 leading-relaxed break-keep">
            <span className="mt-2.5 w-1.5 h-1.5 rounded-full bg-brand-neon shrink-0" />
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}
