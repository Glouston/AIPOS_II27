Министерство образования Республики Беларусь

Учреждение образования

«Брестский Государственный технический университет»

Кафедра ИИТ




**Лабораторная работа №1**

По дисциплине «АиПОС»

Тема: «Организация TCP»



















**Выполнил:**

Студент 3 курса

Группы ИИ-27/24

Ханцевич Г.С.

**Проверил:** 

Кулик А.Д.






Брест 2026

**Вариант 11**

**Цель работы:** Изучить принципы работы TCP по средствам разработки двух программ, а именно, сервер и клиент.

Задание 1:

Реализовать программно сервер. 

Код программы:

import java.io.\*;\
import java.net.\*;\
\
public class Main {\
\
`    `public static final int *PORT* = 5001;\
\
`    `private static final int *CHUNK\_SIZE* = 10;\
\
`    `public static void main(String[] args) throws IOException {\
`        `ServerSocket serverSocket = new ServerSocket(*PORT*);\
`        `System.*out*.println("Сервер запущен: " + serverSocket);\
\
`        `try {\
\
`            `while (true) {\
`                `System.*out*.println("Ожидание подключения клиента...");\
\
`                `Socket socket = serverSocket.accept();\
`                `System.*out*.println("Клиент подключен: " + socket);\
\
`                `try {\
`                    `*handleClient*(socket);\
`                `} finally {\
`                    `System.*out*.println("Закрываем соединение с клиентом...");\
`                    `socket.close();\
`                `}\
`            `}\
`        `} finally {\
`            `serverSocket.close();\
`        `}\
`    `}\
\
`    `private static void handleClient(Socket socket) throws IOException {\
\
`        `InputStream in = socket.getInputStream();\
\
`        `PrintWriter out = new PrintWriter(\
`                `new BufferedWriter(new OutputStreamWriter(socket.getOutputStream())),\
`                `true);\
\
`        `StringBuilder chunk = new StringBuilder(*CHUNK\_SIZE*);\
\
`        `int b;\
`        `while ((b = in.read()) != -1) {\
`            `char c = (char) b;\
`            `chunk.append(c);\
\
`            `if (chunk.length() == *CHUNK\_SIZE*) {\
`                `int checksum = *computeChecksum*(chunk);\
\
`                `System.*out*.println("Принята цепочка: \"" + *escapeControlChars*(chunk.toString())\
`                        `+ "\" -> контрольная сумма = " + checksum);\
\
`                `out.println("Checksum: " + checksum);\
\
`                `chunk.setLength(0);\
`            `}\
`        `}\
`    `}\
\
`    `private static int computeChecksum(CharSequence chunk) {\
`        `int sum = 0;\
`        `for (int i = 0; i < chunk.length(); i++) {\
`            `sum += (int) chunk.charAt(i);\
`        `}\
`        `return sum;\
`    `}\
\
`    `private static String escapeControlChars(String s) {\
`        `StringBuilder sb = new StringBuilder();\
`        `for (char c : s.toCharArray()) {\
`            `if (c == '\n') sb.append("\\n");\
`            `else if (c == '\r') sb.append("\\r");\
`            `else sb.append(c);\
`        `}\
`        `return sb.toString();\
`    `}\
}

**Задание 2:**

**Реализовать программно клиента.**

**Код программы:**

import javax.swing.\*;\
import java.awt.\*;\
import java.awt.event.\*;\
import java.io.\*;\
import java.net.\*;\
import java.text.SimpleDateFormat;\
import java.util.Date;\
\
\
public class TCPClientVariant2 extends JFrame {\
`    `private final JTextArea logArea = new JTextArea();\
`    `private final JTextField inputField = new JTextField();\
`    `private final JButton sendButton = new JButton("Отправить (PgUp)");\
`    `private final JLabel statusLabel = new JLabel("Не подключено. Введите: connect <адрес> <порт> и нажмите PgUp (или кнопку)");\
\
`    `private Socket socket;\
`    `private PrintWriter out;\
`    `private BufferedReader in;\
`    `private volatile boolean connected = false;\
\
`    `private PrintWriter protocolLog;\
`    `private static final String *LOG\_FILE* = "client\_protocol.log";\
`    `private static final SimpleDateFormat *TIME\_FMT* = new SimpleDateFormat("yyyy-MM-dd HH:mm:ss.SSS");\
\
`    `public TCPClientVariant2() throws IOException {\
`        `super("TCP Client - вариант 2");\
\
`        `protocolLog = new PrintWriter(new BufferedWriter(new FileWriter(*LOG\_FILE*, true)), true);\
\
`        `logArea.setEditable(false);\
`        `logArea.setFont(new Font(Font.*MONOSPACED*, Font.*PLAIN*, 13));\
\
`        `setLayout(new BorderLayout());\
`        `add(new JScrollPane(logArea), BorderLayout.*CENTER*);\
\
`        `JPanel bottom = new JPanel(new BorderLayout());\
`        `JLabel inputLabel = new JLabel("Пишите здесь \u2192");\
`        `bottom.add(inputLabel, BorderLayout.*WEST*);\
`        `bottom.add(inputField, BorderLayout.*CENTER*);\
`        `bottom.add(sendButton, BorderLayout.*EAST*);\
`        `add(bottom, BorderLayout.*SOUTH*);\
`        `add(statusLabel, BorderLayout.*NORTH*);\
\
\
`        `inputField.addKeyListener(new KeyAdapter() {\
`            `@Override\
`            `public void keyPressed(KeyEvent e) {\
`                `if (e.getKeyCode() == KeyEvent.*VK\_PAGE\_UP*) {\
`                    `e.consume();\
`                    `handleInput();\
`                `} else {\
\
`                    `System.*out*.println("keyPressed: " + KeyEvent.*getKeyText*(e.getKeyCode())\
`                            `+ " (code=" + e.getKeyCode() + ")");\
`                `}\
`            `}\
`        `});\
\
`        `sendButton.addActionListener(e -> handleInput());\
`        `addWindowListener(new WindowAdapter() {\
`            `@Override\
`            `public void windowClosing(WindowEvent e) {\
`                `closeConnection();\
`                `protocolLog.close();\
`                `dispose();\
`                `System.*exit*(0);\
`            `}\
`        `});\
\
`        `setDefaultCloseOperation(JFrame.*DO\_NOTHING\_ON\_CLOSE*);\
`        `setSize(640, 420);\
`        `setLocationRelativeTo(null);\
`    `}\
\
`    `private void handleInput() {\
`        `String text = inputField.getText();\
`        `inputField.setText("");\
`        `if (text.isEmpty()) return;\
\
`        `if (!connected) {\
`            `if (text.toLowerCase().startsWith("connect ")) {\
`                `String[] parts = text.trim().split("\\s+");\
`                `if (parts.length != 3) {\
`                    `appendScreen("Использование: connect <адрес> <порт>");\
`                    `return;\
`                `}\
`                `try {\
`                    `int port = Integer.*parseInt*(parts[2]);\
`                    `connect(parts[1], port);\
`                `} catch (NumberFormatException ex) {\
`                    `appendScreen("Некорректный номер порта: " + parts[2]);\
`                `} catch (IOException ex) {\
`                    `appendScreen("Не удалось подключиться: " + ex.getMessage());\
`                `}\
`            `} else {\
`                `appendScreen("Нет соединения. Сначала выполните: connect <адрес> <порт>");\
`            `}\
`        `} else {\
`            `out.println(text);\
`            `appendScreen("Отправлено: " + text);\
\
`        `}\
`    `}\
\
`    `private void connect(String address, int port) throws IOException {\
`        `socket = new Socket(address, port);\
`        `out = new PrintWriter(new BufferedWriter(new OutputStreamWriter(socket.getOutputStream())), true);\
`        `in = new BufferedReader(new InputStreamReader(socket.getInputStream()));\
`        `connected = true;\
\
`        `String startTime = *TIME\_FMT*.format(new Date());\
`        `protocolLog.println("[" + startTime + "] Соединение установлено: " + socket);\
`        `appendScreen("Подключено к " + address + ":" + port);\
`        `statusLabel.setText("Подключено к " + address + ":" + port);\
\
`        `Thread reader = new Thread(this::readLoop, "server-reader");\
`        `reader.setDaemon(true);\
`        `reader.start();\
`    `}\
\
`    `private void readLoop() {\
`        `try {\
`            `String line;\
`            `while ((line = in.readLine()) != null) {\
`                `String time = *TIME\_FMT*.format(new Date());\
`                `protocolLog.println("[" + time + "] Получено от сервера: " + line);\
`                `appendScreen("Сервер: " + line);\
`            `}\
`        `} catch (IOException e) {\
`            `appendScreen("Соединение прервано: " + e.getMessage());\
`        `} finally {\
`            `closeConnection();\
`        `}\
`    `}\
\
`    `private void closeConnection() {\
`        `if (!connected) return;\
`        `connected = false;\
`        `String endTime = *TIME\_FMT*.format(new Date());\
`        `protocolLog.println("[" + endTime + "] Соединение завершено.");\
`        `appendScreen("Соединение закрыто.");\
`        `statusLabel.setText("Не подключено. Введите: connect <адрес> <порт> и нажмите PgUp");\
`        `try {\
`            `if (socket != null) socket.close();\
`        `} catch (IOException ignored) {\
`        `}\
`    `}\
\
`    `private void appendScreen(String s) {\
`        `SwingUtilities.*invokeLater*(() -> {\
`            `logArea.append(s + "\n");\
`            `logArea.setCaretPosition(logArea.getDocument().getLength());\
`        `});\
`    `}\
\
`    `public static void main(String[] args) {\
`        `SwingUtilities.*invokeLater*(() -> {\
`            `try {\
`                `TCPClientVariant2 client = new TCPClientVariant2();\
`                `client.setVisible(true);\
`                `client.inputField.requestFocusInWindow();\
`            `} catch (IOException e) {\
`                `JOptionPane.*showMessageDialog*(null, "Не удалось открыть файл протокола: " + e.getMessage());\
`            `}\
`        `});\
`    `}\
}

**Результат работы:**

![](Aspose.Words.b5703be1-6ff0-42f2-987e-92a983a45221.001.png)**\


![](Aspose.Words.b5703be1-6ff0-42f2-987e-92a983a45221.002.png)

**Вывод:**

Изучили принцип работы TCP.
