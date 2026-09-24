export default function BreadIcon({ size = 20, className }: { size?: number; className?: string }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 20 20"
      fill="none"
      className={className}
      aria-hidden="true"
    >
      <path
        d="M4.5 15V9.75C4.5 6.92 6.62 4.9 10 4.9C13.38 4.9 15.5 6.92 15.5 9.75V15H4.5Z"
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path d="M7 8.15L6.35 9.75" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
      <path d="M10 7.45L9.35 9.15" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
      <path d="M13 8.15L12.35 9.75" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
    </svg>
  )
}
