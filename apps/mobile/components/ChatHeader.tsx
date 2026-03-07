import React, { useMemo } from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useSidebar } from '../lib/sidebar-context';
import { useColors } from '../lib/theme-context';
import { ColorTokens } from '../lib/colors';

type Props = {
  title?: string;
  showBack?: boolean;
};

export function ChatHeader({ title = 'ARI', showBack = false }: Props) {
  const { open } = useSidebar();
  const router = useRouter();
  const colors = useColors();
  const styles = useMemo(() => makeStyles(colors), [colors]);

  return (
    <View style={styles.header}>
      <View style={styles.left}>
        <TouchableOpacity
          style={styles.iconBtn}
          onPress={showBack ? () => router.back() : open}
          hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
        >
          <Ionicons
            name={showBack ? 'chevron-back' : 'reorder-three-outline'}
            size={showBack ? 24 : 26}
            color={colors.foreground}
          />
        </TouchableOpacity>
        <Text style={styles.title} numberOfLines={1}>{title}</Text>
      </View>

      <TouchableOpacity
        style={styles.iconBtn}
        onPress={() => router.push('/(app)')}
        hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
      >
        <Ionicons name="create-outline" size={22} color={colors.foreground} />
      </TouchableOpacity>
    </View>
  );
}

const makeStyles = (c: ColorTokens) => StyleSheet.create({
  header: {
    height: 52,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 8,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: c.border,
    backgroundColor: c.background,
  },
  left: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    flex: 1,
  },
  iconBtn: {
    width: 44,
    height: 44,
    alignItems: 'center',
    justifyContent: 'center',
  },
  title: {
    flex: 1,
    fontSize: 17,
    fontWeight: '700',
    color: c.foreground,
  },
});
