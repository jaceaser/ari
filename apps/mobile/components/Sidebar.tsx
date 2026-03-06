import React, { useMemo } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  Animated,
  SafeAreaView,
  SectionList,
  ActivityIndicator,
  Alert,
  Pressable,
  Dimensions,
} from 'react-native';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { listSessions, deleteSession, Session } from '../lib/api';
import { colors } from '../lib/colors';
import { useSidebar, SIDEBAR_WIDTH } from '../lib/sidebar-context';

const { width: SCREEN_WIDTH } = Dimensions.get('window');

type Section = { title: string; data: Session[] };

function groupSessions(sessions: Session[]): Section[] {
  const now = Date.now();
  const DAY = 86400000;
  const groups: Record<string, Session[]> = {
    Today: [],
    Yesterday: [],
    'Previous 7 days': [],
    'Previous 30 days': [],
    Older: [],
  };
  for (const s of sessions) {
    const ts = s.updatedAt ?? s.createdAt ?? 0;
    const age = now - ts;
    if (age < DAY) groups['Today'].push(s);
    else if (age < 2 * DAY) groups['Yesterday'].push(s);
    else if (age < 7 * DAY) groups['Previous 7 days'].push(s);
    else if (age < 30 * DAY) groups['Previous 30 days'].push(s);
    else groups['Older'].push(s);
  }
  return Object.entries(groups)
    .filter(([, items]) => items.length > 0)
    .map(([title, data]) => ({ title, data }));
}

export function SidebarOverlay() {
  const { isOpen, anim, close } = useSidebar();
  const router = useRouter();
  const queryClient = useQueryClient();

  const { data: sessions = [], isLoading } = useQuery({
    queryKey: ['sessions'],
    queryFn: listSessions,
    enabled: isOpen,
  });

  const sections = useMemo(() => groupSessions(sessions), [sessions]);

  const translateX = anim.interpolate({
    inputRange: [0, 1],
    outputRange: [-SIDEBAR_WIDTH, 0],
  });

  const backdropOpacity = anim.interpolate({
    inputRange: [0, 1],
    outputRange: [0, 0.45],
  });

  const handleDelete = (session: Session) => {
    Alert.alert('Delete chat', `Delete "${session.title || 'Untitled'}"?`, [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Delete',
        style: 'destructive',
        onPress: async () => {
          await deleteSession(session.id);
          queryClient.invalidateQueries({ queryKey: ['sessions'] });
        },
      },
    ]);
  };

  const handleNewChat = () => {
    close();
    router.push('/(app)');
  };

  const handleOpenChat = (id: string) => {
    close();
    router.push(`/(app)/chat/${id}`);
  };

  const handleSettings = () => {
    close();
    router.push('/(app)/settings');
  };

  if (!isOpen) return null;

  return (
    <View style={StyleSheet.absoluteFill} pointerEvents="box-none">
      {/* Backdrop */}
      <Animated.View
        style={[styles.backdrop, { opacity: backdropOpacity }]}
        pointerEvents={isOpen ? 'auto' : 'none'}
      >
        <Pressable style={StyleSheet.absoluteFill} onPress={close} />
      </Animated.View>

      {/* Sidebar panel */}
      <Animated.View style={[styles.panel, { transform: [{ translateX }] }]}>
        <SafeAreaView style={styles.safeArea}>
          {/* Header */}
          <View style={styles.header}>
            <View style={styles.logoRow}>
              <View style={styles.logoIcon}>
                <Text style={styles.logoIconText}>A</Text>
              </View>
              <Text style={styles.logoLabel}>ARI</Text>
            </View>
            <TouchableOpacity onPress={handleNewChat} style={styles.newChatBtn}>
              <Ionicons name="create-outline" size={22} color={colors.foreground} />
            </TouchableOpacity>
          </View>

          {/* History list */}
          {isLoading ? (
            <View style={styles.loadingCenter}>
              <ActivityIndicator color={colors.primary} />
            </View>
          ) : (
            <SectionList
              sections={sections}
              keyExtractor={(s) => s.id}
              style={styles.list}
              renderSectionHeader={({ section }) => (
                <Text style={styles.sectionTitle}>{section.title}</Text>
              )}
              renderItem={({ item }) => (
                <TouchableOpacity
                  style={styles.sessionRow}
                  onPress={() => handleOpenChat(item.id)}
                  activeOpacity={0.6}
                >
                  <Text style={styles.sessionTitle} numberOfLines={1}>
                    {item.title || 'Untitled'}
                  </Text>
                  <TouchableOpacity
                    onPress={() => handleDelete(item)}
                    hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
                  >
                    <Ionicons name="trash-outline" size={15} color={colors.border} />
                  </TouchableOpacity>
                </TouchableOpacity>
              )}
              ListEmptyComponent={
                <Text style={styles.emptyText}>No conversations yet</Text>
              }
              contentContainerStyle={{ paddingBottom: 16 }}
            />
          )}

          {/* Footer */}
          <View style={styles.footer}>
            <TouchableOpacity style={styles.footerRow} onPress={handleSettings}>
              <Ionicons name="person-circle-outline" size={22} color={colors.foreground} />
              <Text style={styles.footerLabel}>Account & Settings</Text>
            </TouchableOpacity>
          </View>
        </SafeAreaView>
      </Animated.View>
    </View>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: '#000',
  },
  panel: {
    position: 'absolute',
    top: 0,
    left: 0,
    bottom: 0,
    width: SIDEBAR_WIDTH,
    backgroundColor: colors.sidebarBg,
    borderRightWidth: StyleSheet.hairlineWidth,
    borderRightColor: colors.border,
    shadowColor: '#000',
    shadowOffset: { width: 4, height: 0 },
    shadowOpacity: 0.12,
    shadowRadius: 12,
    elevation: 16,
  },
  safeArea: { flex: 1 },

  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingTop: 8,
    paddingBottom: 12,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
  },
  logoRow: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  logoIcon: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
  },
  logoIconText: { fontSize: 15, fontWeight: '800', color: colors.primaryForeground },
  logoLabel: { fontSize: 17, fontWeight: '700', color: colors.foreground },
  newChatBtn: { padding: 4 },

  list: { flex: 1 },
  sectionTitle: {
    fontSize: 11,
    fontWeight: '600',
    color: colors.mutedForeground,
    textTransform: 'uppercase',
    letterSpacing: 0.6,
    paddingHorizontal: 16,
    paddingTop: 18,
    paddingBottom: 4,
  },
  sessionRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 10,
    gap: 8,
  },
  sessionTitle: {
    flex: 1,
    fontSize: 14,
    color: colors.foreground,
  },
  emptyText: {
    fontSize: 14,
    color: colors.mutedForeground,
    textAlign: 'center',
    marginTop: 32,
  },
  loadingCenter: { flex: 1, alignItems: 'center', justifyContent: 'center' },

  footer: {
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.border,
    paddingHorizontal: 16,
    paddingVertical: 12,
  },
  footerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    paddingVertical: 8,
  },
  footerLabel: { fontSize: 15, color: colors.foreground },
});
