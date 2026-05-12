import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"

// 1. Define Variants using CVA
const cardVariants = cva(
  "rounded-xl border bg-card text-card-foreground shadow",
  {
    variants: {
      variant: {
        default: "bg-card",
        glass: "bg-white/10 backdrop-blur-md border-white/20",
        neon: "border-primary/50 shadow-[0_0_15px_rgba(var(--primary),0.3)]",
      },
      size: {
        default: "p-6",
        sm: "p-4",
        lg: "p-8",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

export interface CustomCardProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof cardVariants> {}

// 2. Component with ForwardRef
const CustomCard = React.forwardRef<HTMLDivElement, CustomCardProps>(
  ({ className, variant, size, ...props }, ref) => (
    <div
      ref={ref}
      // 3. Use 'cn' utility
      className={cn(cardVariants({ variant, size, className }))}
      {...props}
    />
  )
)

// 4. Always set displayName
CustomCard.displayName = "CustomCard"

export { CustomCard, cardVariants }
