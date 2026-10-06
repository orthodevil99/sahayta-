"use client";
import { Car, Cross, HeartHandshake, Languages, LifeBuoy, MoreHorizontal, Package, Soup, Tent, Wrench } from "lucide-react";
import { useI18n } from "../lib/i18n";
import type { SOSCategory, VolunteerSkill } from "../lib/types";

const CAT_ICON: Record<SOSCategory, typeof Cross> = {
  medical: Cross, rescue: LifeBuoy, food: Soup, shelter: Tent, infrastructure: Wrench, other: MoreHorizontal,
};

export default function CategoryChip({ category }: { category: SOSCategory }) {
  const { t } = useI18n();
  const Icon = CAT_ICON[category];
  return (
    <span className="pill border border-line bg-surface text-body">
      <Icon size={15} aria-hidden /> {t(`category.${category}`)}
    </span>
  );
}

const SKILL_ICON: Record<VolunteerSkill, typeof Cross> = {
  medical: Cross, rescue: LifeBuoy, driving: Car, cooking: Soup,
  shelter_mgmt: Tent, translation: Languages, logistics: Package,
  counseling: HeartHandshake, engineering: Wrench,
};

export function SkillIcons({ skills }: { skills: VolunteerSkill[] }) {
  return (
    <span className="inline-flex items-center gap-1" aria-label={skills.join(", ")}>
      {skills.map((s) => {
        const Icon = SKILL_ICON[s] ?? MoreHorizontal;
        return <Icon key={s} size={15} aria-hidden className="text-muted" />;
      })}
    </span>
  );
}
