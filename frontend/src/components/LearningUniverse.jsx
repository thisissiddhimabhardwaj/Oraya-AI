import { Play, Sparkles, ArrowUpRight } from "lucide-react";

export default function LearningUniverse({ compact = false }) {
  return (
    <div
      className={`learning-universe ${compact ? "compact" : ""}`}
      aria-label="An open book unfolds into a universe of ideas"
      role="img"
    >
      <svg viewBox="0 0 720 580" aria-hidden="true">
        <defs>
          <radialGradient id="planet">
            <stop stopColor="#c0ddd9" />
            <stop offset=".65" stopColor="#88b8b6" />
            <stop offset="1" stopColor="#568d91" />
          </radialGradient>
          <linearGradient id="paper" x2="0.7" y2="1">
            <stop stopColor="#fff9e9" />
            <stop offset="1" stopColor="#edc5a0" />
          </linearGradient>
          <linearGradient id="cover">
            <stop stopColor="#eb9873" />
            <stop offset="1" stopColor="#b44c32" />
          </linearGradient>
          <pattern
            id="lines"
            width="16"
            height="16"
            patternUnits="userSpaceOnUse"
          >
            <path d="M0 16h16" stroke="#c3a487" strokeWidth=".7" />
          </pattern>
        </defs>
        <circle cx="388" cy="230" r="185" fill="#f6dfc8" opacity=".45" />
        <ellipse
          cx="395"
          cy="270"
          rx="280"
          ry="87"
          fill="none"
          stroke="#e99070"
          strokeWidth="2"
          transform="rotate(-21 395 270)"
        />
        <g className="universe-globe">
          <circle cx="447" cy="200" r="125" fill="url(#planet)" />
          <path
            d="M380 102l42-19 33 10 17 25-26 25-10 40-28 13-15-24-30-6-13-24zM480 209l43-14 41 28-14 30-24 2-9 39-27 14-18-46-14-29zM389 241l27 6 16 38-24 32-22-14-13-38z"
            fill="#799760"
          />
          <ellipse
            cx="447"
            cy="200"
            rx="65"
            ry="124"
            fill="none"
            stroke="#e1efdd"
            opacity=".35"
          />
          <path
            d="M323 198h248M342 140h208M344 257h204"
            stroke="#e1efdd"
            opacity=".3"
          />
        </g>
        <g
          className="universe-saturn"
          transform="translate(192 118) rotate(-23)"
        >
          <ellipse
            rx="47"
            ry="13"
            fill="none"
            stroke="#ca9960"
            strokeWidth="7"
          />
          <circle r="31" fill="#e7bd88" />
          <path
            d="M-28-11h56M-30 2h60M-25 15h50"
            stroke="#d9a56e"
            strokeWidth="4"
          />
          <path
            d="M-47 0q0 20 94 0"
            fill="none"
            stroke="#f4cc91"
            strokeWidth="5"
          />
        </g>
        <g stroke="#518081" strokeWidth="4" className="universe-molecule">
          <path
            d="M254 292l38-32 39 20 15 46-35 24-39-19zM331 280l28-30M346 326l37 17"
            fill="none"
          />
          {[
            [254, 292, 13, "#eab481"],
            [292, 260, 11, "#edbe76"],
            [331, 280, 15, "#8ab9b4"],
            [346, 326, 12, "#e9856e"],
            [311, 350, 11, "#edbc75"],
            [272, 331, 10, "#abc5ae"],
            [359, 250, 10, "#e9856e"],
            [383, 343, 10, "#8ab9b4"],
          ].map(([cx, cy, r, c]) => (
            <circle
              key={cx}
              {...{ cx, cy, r }}
              fill={c}
              stroke="#fff6e9"
              strokeWidth="2"
            />
          ))}
        </g>
        <g
          className="universe-leaves"
          fill="#8fa276"
          stroke="#687f58"
          strokeWidth="1.5"
        >
          <path
            d="M105 477q-15-86-48-134M103 461q43-61 46-113M600 477q38-70 55-141"
            fill="none"
          />
          {[
            [66, 368, -25],
            [82, 409, -35],
            [123, 407, 35],
            [138, 370, 35],
            [624, 429, 40],
            [644, 383, 40],
            [604, 452, -30],
          ].map(([x, y, r]) => (
            <path
              key={x}
              d="M0 0Q-35-15-18-49Q13-22 0 0Z"
              transform={`translate(${x} ${y}) rotate(${r})`}
            />
          ))}
        </g>
        <ellipse
          cx="367"
          cy="509"
          rx="284"
          ry="18"
          fill="#c7b7a1"
          opacity=".2"
        />
        <path
          d="M90 477Q225 410 359 470Q492 411 638 477L654 504Q485 475 359 512Q232 478 76 503Z"
          fill="url(#cover)"
        />
        <path
          d="M91 477Q233 401 359 468Q494 400 637 477L631 492Q475 451 359 503Q242 452 91 492Z"
          fill="url(#paper)"
          stroke="#c99b77"
          strokeWidth="1.5"
        />
        <path
          d="M105 463Q235 386 359 468Q490 390 620 463L628 481Q482 443 359 497Q239 443 100 481Z"
          fill="#fff3d9"
        />
        <path
          d="M121 447Q239 380 359 468Q484 386 606 447L620 464Q480 425 359 493Q238 424 105 465Z"
          fill="url(#paper)"
        />
        <path
          d="M135 430Q245 370 359 468Q479 370 592 430L609 451Q478 409 359 487Q242 408 120 451Z"
          fill="#fff8e9"
          stroke="#e3c4a2"
        />
        <path
          d="M359 468v35M151 434q106-38 192 35M145 443q104-34 198 34M381 470q92-76 195-34M381 478q96-70 205-33"
          fill="none"
          stroke="#d7b596"
          strokeWidth="1.5"
        />
        <g fill="#e9b552">
          <path d="M600 90l4-14 5 14 13 5-13 5-5 14-4-14-14-5zM135 275l3-10 4 10 10 3-10 4-4 10-3-10-10-4zM559 352l4-10 3 10 10 3-10 4-3 10-4-10-10-4z" />
        </g>
      </svg>
      <div className="universe-video">
        <span className="video-play">
          <Play size={21} fill="currentColor" />
        </span>
        <div className="video-track">
          <i />
        </div>
        <small>Discover a new perspective</small>
      </div>
      <div className="universe-tutor">
        <strong>
          <Sparkles size={19} /> Your AI tutor
        </strong>
        <span>Why does this happen?</span>
        <i>
          <ArrowUpRight size={17} />
        </i>
      </div>
      <span className="universe-orbit-label">A WORLD OF UNDERSTANDING</span>
    </div>
  );
}
