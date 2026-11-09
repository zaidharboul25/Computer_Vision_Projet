import React, { useEffect, useRef } from 'react'
import {
  motion,
  useInView,
  useMotionValue,
  useReducedMotion,
  useSpring,
  type HTMLMotionProps,
  type Variants,
} from 'framer-motion'

export const EASE = [0.22, 1, 0.36, 1] as const

/** Transition de page : fondu + léger glissement. */
export const PageTransition: React.FC<{ children: React.ReactNode; className?: string }> = ({ children, className }) => {
  const reduce = useReducedMotion()
  return (
    <motion.div
      className={className}
      initial={reduce ? false : { opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      exit={reduce ? undefined : { opacity: 0, y: -8 }}
      transition={{ duration: 0.4, ease: EASE }}
    >
      {children}
    </motion.div>
  )
}

const staggerVariants: Variants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.07, delayChildren: 0.05 } },
}
const itemVariants: Variants = {
  hidden: { opacity: 0, y: 18 },
  show: { opacity: 1, y: 0, transition: { duration: 0.5, ease: EASE } },
}

export const Stagger: React.FC<HTMLMotionProps<'div'>> = ({ children, ...rest }) => (
  <motion.div variants={staggerVariants} initial="hidden" animate="show" {...rest}>
    {children}
  </motion.div>
)

export const StaggerItem: React.FC<HTMLMotionProps<'div'>> = ({ children, ...rest }) => (
  <motion.div variants={itemVariants} {...rest}>
    {children}
  </motion.div>
)

/** Apparition au scroll. */
export const Reveal: React.FC<{ children: React.ReactNode; delay?: number; className?: string }> = ({
  children,
  delay = 0,
  className,
}) => {
  const ref = useRef<HTMLDivElement>(null)
  const inView = useInView(ref, { once: true, margin: '-40px' })
  return (
    <motion.div
      ref={ref}
      className={className}
      initial={{ opacity: 0, y: 20 }}
      animate={inView ? { opacity: 1, y: 0 } : undefined}
      transition={{ duration: 0.55, ease: EASE, delay }}
    >
      {children}
    </motion.div>
  )
}

/** Compteur animé (0 → valeur). */
export const AnimatedNumber: React.FC<{
  value: number
  decimals?: number
  suffix?: string
  className?: string
}> = ({ value, decimals = 0, suffix = '', className }) => {
  const ref = useRef<HTMLSpanElement>(null)
  const reduce = useReducedMotion()
  const mv = useMotionValue(reduce ? value : 0)
  const spring = useSpring(mv, { stiffness: 70, damping: 18, mass: 0.8 })
  const inView = useInView(ref, { once: true })

  useEffect(() => {
    if (inView) mv.set(value)
  }, [inView, value, mv])

  useEffect(() => {
    const fmt = (n: number) =>
      n.toLocaleString('fr-FR', { minimumFractionDigits: decimals, maximumFractionDigits: decimals }) + suffix
    if (ref.current) ref.current.textContent = fmt(reduce ? value : 0)
    return spring.on('change', (v) => {
      if (ref.current) ref.current.textContent = fmt(v)
    })
  }, [spring, decimals, suffix, reduce, value])

  return <span ref={ref} className={className} />
}

/** Carte qui se soulève au survol. */
export const HoverLift: React.FC<HTMLMotionProps<'div'>> = ({ children, ...rest }) => (
  <motion.div whileHover={{ y: -3 }} whileTap={{ scale: 0.985 }} transition={{ type: 'spring', stiffness: 400, damping: 26 }} {...rest}>
    {children}
  </motion.div>
)
