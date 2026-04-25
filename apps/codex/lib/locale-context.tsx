'use client'
import { createContext, useContext } from 'react'
import type { Locale, Translations } from './translations'
import { getTranslations } from './translations'

const LocaleContext = createContext<Locale>('en')
export const LocaleProvider = LocaleContext.Provider
export const useLocale = () => useContext(LocaleContext)
export const useTranslations = (): Translations => getTranslations(useLocale())
