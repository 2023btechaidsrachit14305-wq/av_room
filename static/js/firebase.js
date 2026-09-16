import { initializeApp } from "https://www.gstatic.com/firebasejs/12.19.0/firebase-app.js";
import { getAuth, onAuthStateChanged, signInWithEmailAndPassword, createUserWithEmailAndPassword, signOut, getIdToken } from "https://www.gstatic.com/firebasejs/12.19.0/firebase-auth.js";

const firebaseConfig = {
  apiKey: "AIzaSyB5--9ljxriqvIKASw_mvQP8UdU8q6B9ok",
  authDomain: "avroom-7c3cb.firebaseapp.com",
  projectId: "avroom-7c3cb",
  storageBucket: "avroom-7c3cb.firebasestorage.app",
  messagingSenderId: "963718871721",
  appId: "1:963718871721:web:a42ff35586e8d4392807b8",
  measurementId: "G-XQLJZV5NG"
};

const firebaseApp = initializeApp(firebaseConfig);
export const auth = getAuth(firebaseApp);
export { onAuthStateChanged, signInWithEmailAndPassword, createUserWithEmailAndPassword, signOut, getIdToken };
