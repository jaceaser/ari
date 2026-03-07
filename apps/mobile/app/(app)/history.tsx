import React, { useMemo } from 'react';
import {
  View,
  Text,
  SectionList,
  TouchableOpacity,
  StyleSheet,
  SafeAreaView,
  ActivityIndicator,
  Alert,
} from 'react-native';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useColors } from '../../lib/theme-context';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { listSessions, deleteSession, Session } from '../../lib/api';
import { colors } from '../../lib/colors';

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

export default function HistoryScreen() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const colors = useColors();

  const { data: sessions = [], isLoading, isError, refetch } = useQuery({
    queryKey: ['sessions'],
    queryFn: listSessions,
  });

  const sections = useMemo(() => groupSessions(sessions), [sessions]);

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

  if (isLoading) {
    return (
      <SafeAreaView style={styles.safe}>
        <View style={styles.center}>
          <ActivityIndicator size="large" color={colors.primary} />
        </View>
      </SafeAreaView>
    );
  }

  if (isError) {
    return (
      <SafeAreaView style={styles.safe}>
        <View style={styles.header}>
          <Text style={styles.headerTitle}>History</Text>
        </View>
        <View style={styles.center}>
          <Ionicons name="cloud-offline-outline" size={48} color={colors.border} />
          <Text style={[styles.emptyText, { marginTop: 12 }]}>Couldn't load history</Text>
          <Text style={styles.emptyHint}>Check your connection and try again</Text>
          <TouchableOpacity
            style={[styles.retryBtn, { borderColor: colors.primary }]}
            onPress={() => refetch()}
            activeOpacity={0.7}
          >
            <Ionicons name="refresh" size={15} color={colors.primary} style={{ marginRight: 6 }} />
            <Text style={[styles.retryText, { color: colors.primary }]}>Try again</Text>
          </TouchableOpacity>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.safe}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>History</Text>
      </View>

      <SectionList
        sections={sections}
        keyExtractor={(s) => s.id}
        renderSectionHeader={({ section }) => (
          <View style={styles.sectionHeader}>
            <Text style={styles.sectionTitle}>{section.title}</Text>
          </View>
        )}
        renderItem={({ item }) => (
          <TouchableOpacity
            style={styles.row}
            onPress={() => router.push(`/(app)/chat/${item.id}`)}
            activeOpacity={0.6}
          >
            <Ionicons
              name="chatbubble-outline"
              size={16}
              color={colors.mutedForeground}
              style={styles.rowIcon}
            />
            <Text style={styles.rowTitle} numberOfLines={1}>
              {item.title || 'Untitled'}
            </Text>
            <TouchableOpacity
              onPress={() => handleDelete(item)}
              hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
              style={styles.deleteBtn}
            >
              <Ionicons name="ellipsis-horizontal" size={18} color={colors.mutedForeground} />
            </TouchableOpacity>
          </TouchableOpacity>
        )}
        ItemSeparatorComponent={() => <View style={styles.separator} />}
        ListEmptyComponent={
          <View style={styles.empty}>
            <Ionicons name="chatbubbles-outline" size={48} color={colors.border} />
            <Text style={styles.emptyText}>No conversations yet</Text>
            <Text style={styles.emptyHint}>Start a new chat to get going</Text>
          </View>
        }
        refreshing={isLoading}
        onRefresh={refetch}
        stickySectionHeadersEnabled={false}
        contentContainerStyle={sections.length === 0 ? styles.emptyContainer : { paddingBottom: 20 }}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },

  header: {
    height: 52,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.background,
  },
  headerTitle: { fontSize: 17, fontWeight: '700', color: colors.foreground },

  sectionHeader: {
    paddingHorizontal: 16,
    paddingTop: 20,
    paddingBottom: 6,
    backgroundColor: colors.background,
  },
  sectionTitle: {
    fontSize: 12,
    fontWeight: '600',
    color: colors.mutedForeground,
    textTransform: 'uppercase',
    letterSpacing: 0.6,
  },

  row: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 13,
    backgroundColor: colors.background,
  },
  rowIcon: { marginRight: 10, flexShrink: 0 },
  rowTitle: { flex: 1, fontSize: 15, color: colors.foreground },
  deleteBtn: { paddingLeft: 8 },

  separator: {
    height: StyleSheet.hairlineWidth,
    backgroundColor: colors.border,
    marginLeft: 42,
  },

  empty: { alignItems: 'center', paddingTop: 80, gap: 8 },
  emptyText: { fontSize: 17, fontWeight: '600', color: colors.foreground, marginTop: 8 },
  emptyHint: { fontSize: 14, color: colors.mutedForeground },
  emptyContainer: { flex: 1 },
  retryBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 20,
    paddingHorizontal: 20,
    paddingVertical: 10,
    borderRadius: 10,
    borderWidth: 1.5,
  },
  retryText: { fontSize: 15, fontWeight: '600' },
});
