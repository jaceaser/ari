import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useSidebar } from '../lib/sidebar-context';
import { colors } from '../lib/colors';

type Props = {
  title?: string;
  showBack?: boolean;
};

export function ChatHeader({ title = 'ARI', showBack = false }: Props) {
  const { open } = useSidebar();
  const router = useRouter();

  return (
    <View style={styles.header}>
      {/* Left: hamburger or back */}
      <TouchableOpacity
        style={styles.btn}
        onPress={showBack ? () => router.back() : open}
        hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
      >
        <Ionicons
          name={showBack ? 'chevron-back' : 'reorder-three-outline'}
          size={showBack ? 24 : 26}
          color={colors.foreground}
        />
      </TouchableOpacity>

      {/* Center: title */}
      <TouchableOpacity style={styles.titleWrap} activeOpacity={showBack ? 1 : 0.6}>
        <Text style={styles.title} numberOfLines={1}>{title}</Text>
        {!showBack && (
          <Ionicons name="chevron-forward" size={14} color={colors.mutedForeground} style={{ marginTop: 1 }} />
        )}
      </TouchableOpacity>

      {/* Right: compose */}
      <TouchableOpacity
        style={styles.btn}
        onPress={() => router.push('/(app)')}
        hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
      >
        <Ionicons name="create-outline" size={22} color={colors.foreground} />
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  header: {
    height: 52,
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 8,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
    backgroundColor: colors.background,
  },
  btn: {
    width: 44,
    height: 44,
    alignItems: 'center',
    justifyContent: 'center',
  },
  titleWrap: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 3,
  },
  title: {
    fontSize: 17,
    fontWeight: '700',
    color: colors.foreground,
  },
});
