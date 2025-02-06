<template>
    <div class="form-container">
      <h2>Register</h2>
      <input v-model="username" placeholder="Username" />
      <input v-model="password" type="password" placeholder="Password" />
      <button @click="register">Register</button>
      <p v-if="message">{{ message }}</p>
    </div>
</template>

<style scoped>
.form-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 20px;
  margin: 0 auto;
  width: 100%;
  max-width: 400px;
  text-align: center;
}
</style>
  
<script>
  export default {
    data() {
      return {
        username: '',
        password: '',
        message: ''
      };
    },
    methods: {
      async register() {
        const response = await fetch('http://localhost:5000/register', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            username: this.username,
            password: this.password
          })
        });
  
        const data = await response.json();
        this.message = data.msg; // Set the message based on the response
  
        if (response.ok) {
          this.username = ''; // Clear the input fields
          this.password = '';
        }
      }
    }
  };
</script>