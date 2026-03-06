import React, { useState } from 'react';
import {
  View,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  Platform,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { colors } from '../lib/colors';

type Props = {
  onSend: (text: string) => void;
  disabled?: boolean;
};

export function ChatInput({ onSend, disabled }: Props) {
  const [text, setText] = useState('');
  const canSend = !!text.trim() && !disabled;

  const handleSend = () => {
    const trimmed = text.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setText('');
  };

  return (
    <View style={styles.wrapper}>
      <View style={styles.container}>
        <TextInput
          style={styles.input}
          value={text}
          onChangeText={setText}
          placeholder="Message ARI"
          placeholderTextColor={colors.mutedForeground}
          multiline
          maxLength={4000}
          editable={!disabled}
          returnKeyType="default"
        />
        <TouchableOpacity
          style={[styles.sendBtn, canSend && styles.sendBtnActive]}
          onPress={handleSend}
          disabled={!canSend}
          hitSlop={{ top: 6, bottom: 6, left: 6, right: 6 }}
        >
          <Ionicons
            name="arrow-up"
            size={18}
            color={canSend ? colors.primaryForeground : colors.mutedForeground}
          />
        </TouchableOpacity>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrapper: {
    paddingHorizontal: 12,
    paddingTop: 8,
    paddingBottom: Platform.OS === 'ios' ? 4 : 8,
    backgroundColor: colors.background,
  },
  container: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    backgroundColor: colors.muted,
    borderRadius: 26,
    borderWidth: 1,
    borderColor: colors.border,
    paddingLeft: 16,
    paddingRight: 6,
    paddingVertical: 6,
    // shadow
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.06,
    shadowRadius: 4,
    elevation: 2,
  },
  input: {
    flex: 1,
    fontSize: 15,
    lineHeight: 21,
    color: colors.foreground,
    maxHeight: 130,
    paddingVertical: 4,
    marginRight: 4,
  },
  sendBtn: {
    width: 34,
    height: 34,
    borderRadius: 17,
    backgroundColor: colors.border,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 1,
  },
  sendBtnActive: {
    backgroundColor: colors.primary,
  },
});
