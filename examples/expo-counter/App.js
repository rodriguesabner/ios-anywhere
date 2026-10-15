import React, { useState } from 'react';
import { View, Text, Pressable, StyleSheet, StatusBar } from 'react-native';

export default function App() {
  const [count, setCount] = useState(0);
  return (
    <View style={styles.screen}>
      <StatusBar barStyle="light-content" />
      <Text style={styles.badge}>BUILD LOCAL · LINUX</Text>
      <Text style={styles.title}>Expo no iPhone</Text>
      <Text style={styles.description}>Projeto novo, compilado pelo ios-linux.</Text>
      <Text accessibilityLiveRegion="polite" style={styles.count}>{count}</Text>
      <Pressable accessibilityRole="button" accessibilityLabel="Somar um ao contador" style={styles.button} onPress={() => setCount(value => value + 1)}>
        <Text style={styles.buttonText}>Somar +1</Text>
      </Pressable>
      <Pressable accessibilityRole="button" style={styles.reset} onPress={() => setCount(0)}>
        <Text style={styles.resetText}>Zerar contador</Text>
      </Pressable>
      <Text style={styles.footer}>Expo SDK 54 · Build 01</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: '#101827', justifyContent: 'center', alignItems: 'center', padding: 28 },
  badge: { color: '#82efc4', fontSize: 12, fontWeight: '700', letterSpacing: 2 },
  title: { color: '#fff', fontSize: 32, fontWeight: '700', marginTop: 18, textAlign: 'center' },
  description: { color: '#b2bdd0', fontSize: 16, marginTop: 12, textAlign: 'center' },
  count: { color: '#fff', fontSize: 88, fontWeight: '700', marginVertical: 30 },
  button: { backgroundColor: '#82efc4', borderRadius: 16, paddingVertical: 18, paddingHorizontal: 48 },
  buttonText: { color: '#101827', fontSize: 20, fontWeight: '700' },
  reset: { padding: 20, marginTop: 8 },
  resetText: { color: '#c6d4e8', fontSize: 16 },
  footer: { color: '#9caac0', fontSize: 13, marginTop: 30 },
});
